from flask import Flask, render_template, request, jsonify
from azure.mgmt.network import NetworkManagementClient
from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
from flask_sqlalchemy import SQLAlchemy
import datetime

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///migrations.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Migration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    resource_group_name = db.Column(db.String(100), nullable=False)
    vnet_name = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(50), nullable=False)
    migration_date = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)

db.create_all()


@app.route('/subscriptions', methods=['GET'])
def get_subscriptions():
    try:
        subscriptions = list_subscriptions()
        return jsonify({'success': True, 'subscriptions': subscriptions})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/vpn_vnets', methods=['GET'])
def get_vpn_vnets():
    subscription_id = request.args.get('subscription_id', '')
    if not subscription_id:
        return jsonify({'success': False, 'message': 'No subscription_id provided'})

    try:
        vpn_vnets = list_vpn_vnets(subscription_id)
        return jsonify({'success': True, 'vpn_vnets': vpn_vnets})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

# Add these new functions to perform the required tasks

def list_subscriptions():
    subscriptions = []
    for subscription in resource_client.subscriptions.list():
        subscriptions.append({
            'subscription_id': subscription.subscription_id,
            'display_name': subscription.display_name
        })
    return subscriptions

def list_vpn_vnets(subscription_id):
    # Set up the Azure clients with the specified subscription_id
    network_client = NetworkManagementClient(credential, subscription_id)

    vpn_vnets = []
    for resource_group in resource_client.resource_groups.list():
        for vnet in network_client.virtual_networks.list(resource_group.name):
            if is_vnet_using_vpn_gateway(network_client, resource_group.name, vnet.name):
                vpn_vnets.append({
                    'resource_group': resource_group.name,
                    'name': vnet.name
                })
    return vpn_vnets



def is_vnet_using_vpn_gateway(network_client, resource_group_name, vnet_name):
    # Fetch all virtual network gateways in the resource group
    gateways = network_client.virtual_network_gateways.list(resource_group_name)

    for gateway in gateways:
        if gateway.virtual_network.name == vnet_name and gateway.gateway_type == 'Vpn':
            return True
    return False

@app.route('/migration_data', methods=['GET'])
def get_migration_data():
    migrations = Migration.query.all()
    migration_list = []
    for migration in migrations:
        migration_list.append({
            'resource_group_name': migration.resource_group_name,
            'vnet_name': migration.vnet_name,
            'status': migration.status,
            'migration_date': migration.migration_date.strftime('%Y-%m-%d %H:%M:%S')
        })
    return jsonify({'success': True, 'migrations': migration_list})

@app.route('/migrate', methods=['POST'])
def migrate_vnet():
    subscription_id = request.form.get('subscription_id', '')
    resource_group_name = request.form.get('resource_group_name', '')
    vnet_name = request.form.get('vnet_name', '')

    if not (subscription_id and resource_group_name and vnet_name):
        return jsonify({'success': False, 'message': 'Missing required information'})

    # Perform the migration
    try:
        migrate_vnet_to_express_route(subscription_id, resource_group_name, vnet_name)
        migration = Migration(resource_group_name=resource_group_name, vnet_name=vnet_name, status='Migrated')
        db.session.add(migration)
        db.session.commit()
        return jsonify({'success': True, 'message': 'VNet migration successful'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

def migrate_vnet_to_express_route(subscription_id, resource_group_name, vnet_name):
    # Set up the Azure clients with the specified subscription_id
    network_client = NetworkManagementClient(credential, subscription_id)
    
    # Fetch the virtual network
    vnet = network_client.virtual_networks.get(resource_group_name, vnet_name)

    # Fetch the VPN Gateway associated with the virtual network
    vpn_gateway = None
    gateways = network_client.virtual_network_gateways.list(resource_group_name)
    for gateway in gateways:
        if gateway.virtual_network.name == vnet_name and gateway.gateway_type == 'Vpn':
            vpn_gateway = gateway
            break

    if not vpn_gateway:
        raise Exception(f"No VPN Gateway found for VNet '{vnet_name}'")

    # Create an ExpressRoute Gateway with the same settings as the VPN Gateway
    express_route_gateway_params = {
        'location': vpn_gateway.location,
        'sku': {
            'name': 'Standard', # Choose the appropriate SKU based on the requirements
            'tier': 'Standard'
        },
        'gateway_type': 'ExpressRoute',
        'vpn_type': 'RouteBased',
        'enable_bgp': vpn_gateway.enable_bgp,
        'active_active': vpn_gateway.active_active,
        'virtual_network': {
            'id': vnet.id
        }
    }
    express_route_gateway_creation = network_client.virtual_network_gateways.create_or_update(resource_group_name, f"{vnet_name}-ER-GW", express_route_gateway_params)
    express_route_gateway_creation.wait()

    # Delete the existing VPN Gateway
    network_client.virtual_network_gateways.delete(resource_group_name, vpn_gateway.name).wait()

    # Update the vNet connections to use the newly created ExpressRoute Gateway
    connections = network_client.connections.list(resource_group_name)
    for connection in connections:
        if connection.virtual_network_gateway1.id == vpn_gateway.id:
            connection.virtual_network_gateway1 = {
                'id': express_route_gateway_creation.result().id
            }
            network_client.connections.create_or_update(resource_group_name, connection.name, connection).wait()

if __name__ == '__main__':
    app.run(debug=True)