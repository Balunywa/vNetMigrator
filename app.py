import logging
from flask import Flask, render_template, request, jsonify
from azure.identity import DefaultAzureCredential, ClientSecretCredential
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.subscription import SubscriptionClient
from azure.mgmt.resource import ResourceManagementClient

app = Flask(__name__)

# Set your Azure AD credentials
tenant_id = "86c63279-22a0-4ae4-8f75-b916ba629445"
client_id = "541ff0e0-6f7d-4137-a0c8-eec29fee76e2"
client_secret = "pEO8Q~7XqCTztX7Yk8OqnNFGJzGB3LlulKbjtaKm"

# Authenticate using the ClientSecretCredential
credential = ClientSecretCredential(tenant_id, client_id, client_secret)

# Set up the Azure clients
subscription_id = "c8bc39b5-8f1b-4d8e-92e3-35e2a5bb8c31"
resource_client = ResourceManagementClient(credential, subscription_id)
network_client = NetworkManagementClient(credential, subscription_id)

logging.basicConfig(level=logging.INFO)


@app.route('/')
def index():
    # Fetch subscriptions from Azure
    subscriptions = get_subscriptions()
    return render_template('index.html', subscriptions=subscriptions)


@app.route('/subscriptions', methods=['GET'])
def get_subscriptions():
    subscription_client = SubscriptionClient(credential)
    subscriptions = subscription_client.subscriptions.list()
    result = []
    for sub in subscriptions:
        result.append({
            'subscription_id': sub.subscription_id,
            'display_name': sub.display_name
        })
    return jsonify(result)


@app.route('/vnets', methods=['GET'])
def get_vnets():
    subscription_id = request.args.get('subscription_id')
    vnets = resource_client.resources.list(filter=f"subscriptionId eq '{subscription_id}' and resourceType eq 'Microsoft.Network/virtualNetworks'")
    result = []
    for vnet in vnets:
        result.append({
            'id': vnet.id,
            'name': vnet.name,
            'resource_group': vnet.id.split('/')[4]
        })
    return jsonify(result)


@app.route('/virtualwans', methods=['GET'])
def get_virtual_wans():
    subscription_id = request.args.get('subscription_id')
    virtual_wans = network_client.virtual_wans.list()
    result = []
    for vwan in virtual_wans:
        result.append({
            'id': vwan.id,
            'name': vwan.name,
            'resource_group': vwan.id.split('/')[4],
            'location': vwan.location
        })
    return jsonify(result)

@app.route('/vwanhubs', methods=['GET'])
def get_vwan_hubs_endpoint():
    vwan_id = request.args.get('vwan_id')
    subscription_id = request.args.get('subscription_id')
    return jsonify(get_vwan_hubs(vwan_id, subscription_id))


def get_vwan_hubs(vwan_id, subscription_id):
    try:
        resource_group = vwan_id.split('/')[4]
        vwan_name = vwan_id.split('/')[-1]

        network_client = NetworkManagementClient(credential, subscription_id)
        vwan_hubs = network_client.virtual_hubs.list(resource_group_name=resource_group)
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



@app.route('/migrate', methods=['GET', 'POST'])
def migrate():
    if request.method == 'GET':
        return render_template('migrate.html')
    elif request.method == 'POST':
        # Fetch data from the frontend
        data = request.get_json()
        subscription_id = data['subscription_id']
        vnet = data['vnet']
        vwan_hub_name = data['vwan_hub_name']
        vnet_resource_group = data['vnet_resource_group']
        vwan_resource_group = data['vwan_resource_group']
        propagate_route_tables = data['propagate_route_tables']

        # Perform vNet migration to vWAN Hub
        migrate_vnet_to_vwan_hub(subscription_id, vnet, vnet_resource_group, vwan_resource_group, vwan_hub_name, propagate_route_tables)

        return jsonify({'result': 'Migration initiated successfully.'})



def migrate_vnet_to_vwan_hub(subscription_id, vnet, vnet_resource_group, vwan_resource_group, vwan_hub_name, propagate_route_tables):
    vnet_id = vnet['id']
    connection_name = f"{vnet_id}-{vwan_hub_name}-connection"
    default_route_table_id = get_default_route_table_id(vwan_hub_name, vwan_resource_group)
    if not default_route_table_id:
        logging.error("Default route table ID not found for the specified vWAN Hub.")
        return

    migrate_vnet_to_vwan_hub_single(subscription_id, vnet_id, vnet_resource_group, vwan_resource_group,
                                    vwan_hub_name, connection_name, default_route_table_id, propagate_route_tables)


def migrate_vnet_to_vwan_hub_single(subscription_id, vnet_id, vnet_resource_group, vwan_resource_group, vwan_hub_name,
                                    connection_name, default_route_table_id, propagate_route_tables):
    response = network_client.hub_virtual_network_connections.begin_create_or_update(
        resource_group_name=vwan_resource_group,
        virtual_hub_name=vwan_hub_name,
        connection_name=connection_name,
        hub_virtual_network_connection_parameters={
            "properties": {
                "enableInternetSecurity": False,
                "remoteVirtualNetwork": {
                    "id": vnet_id
                },
                "routingConfiguration": {
                    "associatedRouteTable": {
                        "id": default_route_table_id
                    },
                    "propagatedRouteTables": {
                        "ids": [
                            {
                                "id": default_route_table_id
                            }
                        ],
                        "labels": {
                            "default": propagate_route_tables
                        }
                    },
                }
            },
        },
    ).result()

    logging.info(f"Migration response: {response}")


if __name__ == '__main__':
    app.run()


