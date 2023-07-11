import os
import logging
import requests
from flask import Flask, render_template, request, jsonify
from azure.identity import DefaultAzureCredential, ClientSecretCredential
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.subscription import SubscriptionClient
from azure.mgmt.resource import ResourceManagementClient


app = Flask(__name__)

# Set your Azure AD credentials
tenant_id = "86c63279-22a0-4ae4-8f75-b916ba629445"
client_id = "932bb932-8e38-496c-be32-3fd55ca3d233"
client_secret = "sPn8Q~omelXdf1niniXJZ5YNEFdzczsLZUrCFcGl"

# Authenticate using the ClientSecretCredential
credential = ClientSecretCredential(tenant_id, client_id, client_secret)

# Set up the Azure clients
subscription_id = "c8bc39b5-8f1b-4d8e-92e3-35e2a5bb8c31"
resource_client = ResourceManagementClient(credential, subscription_id)


logging.basicConfig(level=logging.INFO)


def get_access_token():
    credential = DefaultAzureCredential()
    token = credential.get_token("https://graph.microsoft.com/.default")
    return token.token


def get_subscriptions():
    try:
        subscription_client = SubscriptionClient(credential)
        subscriptions = subscription_client.subscriptions.list()
        return [sub.as_dict() for sub in subscriptions]
    except Exception as e:
        logging.error(f"Failed to get subscriptions: {e}")
        raise e


def get_vnets(subscription_id):
    try:
        vnets = resource_client.resources.list(filter="resourceType eq 'Microsoft.Network/virtualNetworks'")
        return [vnet.as_dict() for vnet in vnets]
    except Exception as e:
        logging.error(f"Failed to get vNets: {e}")
        raise e


def get_virtual_wans():
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
        get_vwan_hubs(vwan.id)

    return result


def get_vwan_hubs(vwan_id):
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


def migrate_vnet_to_vwan_hub(vnets, spkrg, vwanrg, vhubname):
    try:
        network_client = NetworkManagementClient(credential, subscription_id)

        for vnet_name in vnets:
            vnet_resource_group = spkrg
            vnet = network_client.virtual_networks.get(vnet_resource_group, vnet_name)
            vnet_id = vnet.id

            network_client.hub_virtual_network_connections.begin_create_or_update(
                vwanrg,
                vhubname,
                vnet_name,
                {
                    'remote_virtual_network': {
                        'id': vnet_id
                    }
                }
            )
    except Exception as e:
        logging.error(f"Failed to migrate vNet: {e}")
        raise e


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/subscriptions', methods=['GET'])
def subscriptions():
    try:
        subs = get_subscriptions()
        return jsonify(subs)
    except Exception as e:
        logging.error(f"Failed to retrieve subscriptions: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/vnets', methods=['POST'])
def vnets():
    try:
        data = request.get_json()
        subscription_id = data['subscription_id']
        vnets = get_vnets(subscription_id)
        return jsonify(vnets)
    except Exception as e:
        logging.error(f"Failed to retrieve vNets: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/virtualwans', methods=['POST'])
def virtualwans():
    try:
        data = request.get_json()
        virtual_wans = get_virtual_wans()
        return jsonify(virtual_wans)
    except Exception as e:
        logging.error(f"Failed to retrieve Virtual WANs: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/vwanhubs', methods=['POST'])
def vwanhubs():
    try:
        data = request.get_json()
        vwan_id = data['vwan_id']
        vwan_hubs = get_vwan_hubs(vwan_id)
        return jsonify(vwan_hubs)
    except Exception as e:
        logging.error(f"Failed to retrieve vWAN Hubs: {e}")
        return jsonify({'error': str(e)}), 500


@app.route("/migrate", methods=["GET", "POST"])
def migrate():
    if request.method == "GET":
        return render_template("migrate.html")
    elif request.method == "POST":
        try:
            data = request.get_json()
            logging.info(f"Received data: {data}")

            vnets = data["vnets"]
            spkrg = data["spkrg"]
            vwanrg = data["vwanrg"]
            vhubname = data["vhubname"]

            # Perform migration operation here...
            migrate_vnet_to_vwan_hub(vnets, spkrg, vwanrg, vhubname)

            return jsonify({"result": "Migration successful"})

        except KeyError as e:
            return jsonify({"error": f"Missing parameter: {str(e)}"}), 400
        except Exception as e:
            logging.error(f"Failed to migrate vNet: {e}")
            return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)

    
