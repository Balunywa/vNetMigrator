import argparse
from azure.identity import ClientSecretCredential
from azure.mgmt.network import NetworkManagementClient
import logging

# Set your Azure AD credentials
tenant_id = "86c63279-22a0-4ae4-8f75-b916ba629445"
client_id = "932bb932-8e38-496c-be32-3fd55ca3d233"
client_secret = "sPn8Q~omelXdf1niniXJZ5YNEFdzczsLZUrCFcGl"

# Authenticate using the ClientSecretCredential
credential = ClientSecretCredential(tenant_id, client_id, client_secret)

logging.basicConfig(level=logging.INFO)

def main(args):
    client = NetworkManagementClient(
        credential=credential,
        subscription_id=args.subscription_id,
    )

    # Construct default route table ID
    default_route_table_id = f"{args.virtual_hub_id}/hubRouteTables/default"

    response = client.hub_virtual_network_connections.begin_create_or_update(
        resource_group_name=args.resource_group,
        virtual_hub_name=args.virtual_hub,
        connection_name=args.connection_name,
        hub_virtual_network_connection_parameters={
            "properties": {
                "enableInternetSecurity": False,
                "remoteVirtualNetwork": {
                    "id": args.remote_virtual_network_id
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
                    }
                },
            }
        },
    ).result()
    print(response)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--subscription_id", required=True)
    parser.add_argument("--resource_group", required=True)
    parser.add_argument("--virtual_hub", required=True)
    parser.add_argument("--virtual_hub_id", required=True)
    parser.add_argument("--connection_name", required=True)
    parser.add_argument("--remote_virtual_network_id", required=True)
    args = parser.parse_args()
    main(args)



