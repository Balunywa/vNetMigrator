import os
import logging
from flask import Flask, render_template, request, jsonify
from azure.identity import DefaultAzureCredential
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.subscription import SubscriptionClient
from azure.mgmt.resource import ResourceManagementClient
from azure.identity import ClientSecretCredential
import json

app = Flask(__name__)

# Set your Azure AD credentials


# Authenticate using the ClientSecretCredential
credential = ClientSecretCredential(tenant_id, client_id, client_secret)

# Get an access token with the required scope
token = credential.get_token("https://graph.microsoft.com/.default")

# Set up the headers for the Microsoft Graph API request
headers = {
    "Authorization": f"Bearer {token.token}",
    "Content-Type": "application/json"
}

# Define the Graph API endpoint for listing service principals
service_principals_url = "https://graph.microsoft.com/v1.0/servicePrincipals"

subscription_id = "c8bc39b5-8f1b-4d8e-92e3-35e2a5bb8c31"

resource_client = ResourceManagementClient(credential, subscription_id)


logging.basicConfig(level=logging.INFO)

def migrate_vnet_to_vwan_hub(credential, subscription_id, spkrg, spkvnetname, spkpeeringname, vwanrg, vhubname):
    try:
        network_client = NetworkManagementClient(credential, subscription_id)

        vnet = network_client.virtual_networks.get(spkrg, spkvnetname)
        vnetid = vnet.id

        network_client.virtual_network_peerings.begin_update(
            spkrg,
            spkvnetname,
            spkpeeringname,
            {
                'use_remote_gateways': False
            }
        )

        network_client.hub_virtual_network_connections.begin_create_or_update(
            vwanrg,
            vhubname,
            spkvnetname,
            {
                'remote_virtual_network': {
                    'id': vnetid
                }
            }
        )
    except Exception as e:
        logging.error(f"Failed to migrate vNet: {e}")
        raise e
    
def get_subscriptions(credential):
    try:
        subscription_client = SubscriptionClient(credential)
        subscriptions = subscription_client.subscriptions.list()
        return [sub.as_dict() for sub in subscriptions]
    except Exception as e:
        logging.error(f"Failed to get subscriptions: {e}")
        raise e
    
def get_vnets(credential, subscription_id):
    try:
        resource_client = ResourceManagementClient(credential, subscription_id)
        vnets = resource_client.resources.list(filter="resourceType eq 'Microsoft.Network/virtualNetworks'")
        return [vnet.as_dict() for vnet in vnets]
    except Exception as e:
        logging.error(f"Failed to get vNets: {e}")
        raise e

def get_virtual_wans(credential, subscription_id):
    network_client = NetworkManagementClient(credential, subscription_id)
    virtual_wans = network_client.virtual_wans.list()
    result = []

    for vwan in virtual_wans:
        result.append({
            'id': vwan.id,
            'name': vwan.name,
            'resource_group': vwan.id.split('/')[4],
            'location': vwan.location
        })

        # Get vWAN Hubs for each vWAN
        get_vwan_hubs(credential, subscription_id, vwan.id)

    return result

def get_vwan_hubs(credential, subscription_id, vwan_id):
    try:
        resource_group = vwan_id.split('/')[4]
        vwan_name = vwan_id.split('/')[-1]

        network_client = NetworkManagementClient(credential, subscription_id)
        vwan_hubs = network_client.virtual_hubs.list()
        result = []
        
        for vhub in vwan_hubs:
            if vhub.virtual_wan and vhub.virtual_wan.id == vwan_id:
                result.append({
                    'id': vhub.id,
                    'name': vhub.name
                })

        if len(result) == 0:
            print(f"No vWAN Hubs for vWAN ID '{vwan_id}'")
        else:
            print(f"vWAN Hubs for vWAN ID '{vwan_id}': {result}")
        
        return result  # Return the list of dictionaries
    except Exception as e:
        print(f"Failed to get vWAN Hubs: {e}")
        return []  # Return an empty list as fallback




@app.route('/')
def index():
    return render_template('index.html')



@app.route('/subscriptions', methods=['GET'])
def subscriptions():
    try:
        subs = get_subscriptions(credential)
        return jsonify(subs)
    except Exception as e:
        logging.error(f"Failed to retrieve subscriptions: {e}")
        return jsonify({'error': str(e)}), 500  
    
    
@app.route('/vnets', methods=['POST'])
def vnets():
    try:
        data = request.get_json()
        subscription_id = data['subscription_id']
        vnets = get_vnets(credential, subscription_id)
        return jsonify(vnets)
    except Exception as e:
        logging.error(f"Failed to retrieve vNets: {e}")
        return jsonify({'error': str(e)}), 500
    
    
@app.route('/virtualwans', methods=['POST'])
def virtualwans():
    try:
        data = request.get_json()
        subscription_id = data['subscription_id']
        virtual_wans = get_virtual_wans(credential, subscription_id)
        return jsonify(virtual_wans)
    except Exception as e:
        logging.error(f"Failed to retrieve Virtual WANs: {e}")
        return jsonify({'error': str(e)}), 500 
    

@app.route('/vwanhubs', methods=['POST'])
def vwanhubs():
    try:
        data = request.get_json()
        vwan_id = data['vwan_id']
        subscription_id = data['subscription_id']  # Add subscription_id
        logging.info(f"Requested vWAN ID: {vwan_id}")
        vwan_hubs = get_vwan_hubs(credential, subscription_id, vwan_id)  # Pass subscription_id
        logging.info(f"Retrieved vWAN Hubs: {vwan_hubs}")
        return jsonify(vwan_hubs)
    except Exception as e:
        logging.error(f"Failed to retrieve vWAN Hubs: {e}")
        return jsonify({'error': str(e)}), 500





@app.route('/migrate', methods=['GET', 'POST'])
def migrate():
    if request.method == 'GET':
        return render_template('migrate.html')

    try:
        data = request.get_json()
        subscription_id = data.get('subscription_id')
        spkrg = data.get('spkrg')
        spkvnetname = data.get('spkvnetname')
        spkpeeringname = data.get('spkpeeringname')
        vwanrg = data.get('vwanrg')
        vhubname = data.get('vhubname')
        if not all([subscription_id, spkrg, spkvnetname, spkpeeringname, vwanrg, vhubname]):
            raise ValueError("Missing required fields")
        migrate_vnet_to_vwan_hub(
            credential,
            subscription_id,
            spkrg,
            spkvnetname,
            spkpeeringname,
            vwanrg,
            vhubname
        )
        return jsonify({'result': 'success'})
    except ValueError as e:
        logging.error(f"Invalid input data: {e}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logging.error(f"Failed to migrate vNet: {e}")
        return jsonify({'error': str(e)})
                             
if __name__ == '__main__':
    app.run(debug=True)