import os
import logging
from azure.identity import DefaultAzureCredential, ClientSecretCredential
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.subscription import SubscriptionClient
from azure.mgmt.resource import ResourceManagementClient

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

def get_subscriptions(credential):
    subscription_client = SubscriptionClient(credential)
    subscriptions = subscription_client.subscriptions.list()
    return [sub.as_dict() for sub in subscriptions]

def get_vnets(subscription_id):
    vnets = resource_client.resources.list(filter="resourceType eq 'Microsoft.Network/virtualNetworks'")
    return [vnet.as_dict() for vnet in vnets]

def get_virtual_wans(subscription_id):
    virtual_wans = network_client.virtual_wans.list()
    result = []
    for vwan in virtual_wans:
        result.append({
            'id': vwan.id,
            'name': vwan.name,
            'resource_group': vwan.id.split('/')[4],
            'location': vwan.location
        })
    return result

def get_vwan_hubs(vwan_id, subscription_id):
    vwan_hubs = network_client.virtual_hubs.list()
    result = []
    for vhub in vwan_hubs:
        if vhub.virtual_wan and vhub.virtual_wan.id == vwan_id:
            result.append({
                'id': vhub.id,
                'name': vhub.name
            })
    return result

def get_default_route_table_id(vwan_hub_name, vwan_resource_group):
    vwan_hubs = network_client.virtual_hubs.list()
    for vhub in vwan_hubs:
        if vhub.name == vwan_hub_name and vhub.id.split('/')[4] == vwan_resource_group:
            return vhub.route_table.id
    return None


def migrate_vnet_to_vwan_hub(vnet_id, vnet_resource_group, vwan_resource_group, vwan_hub_name, connection_name, default_route_table_id):
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
                        ]
                    },
                }
            },
        },
    ).result()

    logging.info(f"Migration response: {response}")

if __name__ == '__main__':
    # Define your data here
    vnet_id = "/subscriptions/c8bc39b5-8f1b-4d8e-92e3-35e2a5bb8c31/resourceGroups/TAACS-Connectivity-RG/providers/Microsoft.Network/virtualNetworks/Contivity-DR"
    vnet_resource_group = "TAACS-Connectivity-RG"
    vwan_resource_group = "TAACS-Connectivity-RG"
    vwan_hub_name = "TAACS-Connectivity-East-US"
    connection_name = "migration-connection"
    default_route_table_id = "/subscriptions/c8bc39b5-8f1b-4d8e-92e3-35e2a5bb8c31/resourceGroups/TAACS-Connectivity-RG/providers/Microsoft.Network/virtualHubs/TAACS-Connectivity-East-US/hubRouteTables/default"

    # Perform vNet migration to vWAN Hub
    migrate_vnet_to_vwan_hub(vnet_id, vnet_resource_group, vwan_resource_group, vwan_hub_name, connection_name, default_route_table_id)


