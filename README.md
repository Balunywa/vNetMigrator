# Azure Network Migration Tool

This is a Flask-based web application that simplifies the process of migrating Azure vNets from using VPN Gateways to Express Route Gateways.

## Prerequisites

- Python 3.6 or higher
- Azure CLI
- Azure subscription with vNets, VPN Gateway, and ExpressRoute Gateway
- Azure SQL Database

## Installation

1. Clone the repository:
git clone https://github.com/your_username/azure-network-migration-tool.git


2. Change into the project directory:
cd azure-network-migration-tool


3. Create a virtual environment and activate it:
python -m venv venv
source venv/bin/activate # For Linux and macOS
venv\Scripts\activate # For Windows


7. Open a web browser and navigate to [http://127.0.0.1:5000/](http://127.0.0.1:5000/).

## Usage

1. Select the desired Azure subscription.
2. Select the vNet you wish to migrate.
3. Click the 'Migrate' button to initiate the migration process.

The migration status and details will be displayed on the Migration Dashboard.

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## License

[MIT](https://choosealicense.com/licenses/mit/)
