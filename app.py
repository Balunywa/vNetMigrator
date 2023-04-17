from flask import Flask, render_template

from flask import Flask, render_template, request, jsonify
#from azure_sdk_migration import migrate_resources, rollback_resources
from azure.mgmt.network import NetworkManagementClient
from azure.identity import DefaultAzureCredential
from azure.mgmt.subscription import SubscriptionClient
from azure.mgmt.resource import ResourceManagementClient

app = Flask(__name__)

def migrate_vnet_to_vwan_hub(subscription_id, spkrg, spkvnetname, spkpeeringname, vwanrg, vhubname):
    # Authenticate and create network management client
    credential = DefaultAzureCredential()
    network_client = NetworkManagementClient(credential, subscription_id)

    # Get Spoke VNET ResourceID
    vnet = network_client.virtual_networks.get(spkrg, spkvnetname)
    vnetid = vnet.id

    # Set UseRemoteGateways to False
    network_client.virtual_network_peerings.begin_update(
        spkrg,
        spkvnetname,
        spkpeeringname,
        {
            'use_remote_gateways': False
        }
    )

    # Configure VWAN HUB Virtual Network Connection
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


def get_subscriptions():
    credential = DefaultAzureCredential()
    subscription_client = SubscriptionClient(credential)
    subscriptions = subscription_client.subscriptions.list()
    return [sub.as_dict() for sub in subscriptions]

def get_vnets(subscription_id):
    credential = DefaultAzureCredential()
    resource_client = ResourceManagementClient(credential, subscription_id)
    vnets = resource_client.resources.list_by_resource_group(filter="resourceType eq 'Microsoft.Network/virtualNetworks'")
    return [vnet.as_dict() for vnet in vnets]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/subscriptions', methods=['GET'])
def subscriptions():
    subs = get_subscriptions()
    return jsonify(subs)

@app.route('/vnets', methods=['POST'])
def vnets():
    subscription_id = request.form['subscription_id']
    vnets = get_vnets(subscription_id)
    return jsonify(vnets)
@app.route('/migrate', methods=['GET', 'POST'])
def migrate():
    if request.method == 'POST':
        data = request.get_json()
        migrate_vnet_to_vwan_hub(
            data['subscription_id'],
            data['spkrg'],
            data['spkvnetname'],
            data['spkpeeringname'],
            data['vwanrg'],
            data['vhubname']
        )
        return jsonify({'result': 'success'})
    return render_template('migrate.html')


@app.route('/rollback', methods=['GET', 'POST'])
def rollback():
    if request.method == 'POST':
        data = request.get_json()
        rollback_resources(data)
        return jsonify({'result': 'success'})
    return render_template('rollback.html')

if __name__ == '__main__':
    app.run(debug=True)