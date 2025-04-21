from flask import Flask, request, jsonify,url_for, render_template
from web3 import Web3
import json
import os
from web3.middleware import ExtraDataToPOAMiddleware
from solcx import compile_standard, install_solc
from werkzeug.utils import secure_filename
from whatsapp import  main_send_message
import logging
import time
import requests
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
from dotenv import load_dotenv
from flask_cors import CORS
from flasgger import Swagger
from twilio.rest import Client
from datetime import datetime

app = Flask(__name__)
CORS(app)  
swagger = Swagger(app)


TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = '+18623754945'

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


request_data = {}

auth_completed = {}
load_dotenv()

pinata_api = os.getenv('PINATA_API_KEY')
pinata_url = os.getenv('PINATA_API_URL')
pinata_secret = os.getenv('PINATA_API_SECRET')

print(pinata_api,pinata_url,pinata_secret)


try:
    install_solc("0.8.0")
    print("Solidity compiler installed successfully")
except Exception as e:
    print(f"Warning: Could not install Solidity compiler: {e}")

with open("sl.sol", "r") as f:
    source = f.read()

SOLIDITY_SOURCE = source


def compile_and_deploy_contract():
    print("Compiling and deploying contract...")
    try:
        # Compile the Solidity code
        compiled_sol = compile_standard(
            {
                "language": "Solidity",
                "sources": {
                    "UserAuthentication.sol": {
                        "content": SOLIDITY_SOURCE
                    }
                },
                "settings": {
                    "outputSelection": {
                        "*": {"*": ["abi", "metadata", "evm.bytecode", "evm.sourceMap"]}
                    }
                },         
            },
            solc_version="0.8.0",
        )
        
        print("Contract compiled successfully")
        
        
        contract_data = compiled_sol["contracts"]["UserAuthentication.sol"]["UserAuthentication"]
        bytecode = contract_data["evm"]["bytecode"]["object"]
        abi = contract_data["abi"]
        
        
        with open("less.json", "w") as f:
            json.dump(abi, f)
            
        print("ABI saved to file")
        
        
        w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:8545"))
        if not w3.is_connected():
            print("Error: Cannot connect to Ganache. Please ensure it's running.")
            return None, None
            
        print(f"Connected to blockchain: {w3.is_connected()}")
        w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
       
        try:
            account = w3.eth.accounts[0]
            w3.eth.default_account = account
            print(f"Using account: {account}")
            balance = w3.eth.get_balance(account)
            print(f"Account balance: {w3.from_wei(balance, 'ether')} ETH")
        except Exception as e:
            print(f"Account error: {e}")
            return None, None
        
        
        try:
            Contract = w3.eth.contract(abi=abi, bytecode=bytecode)
            print("Sending contract deployment transaction...")
            
            
            tx = Contract.constructor().build_transaction({
                'from': account,
                'nonce': w3.eth.get_transaction_count(account),
                'gas': 2000000,
                'gasPrice': w3.eth.gas_price
            })
            
           
            tx_hash = w3.eth.send_transaction(tx)
            print(f"Deployment transaction sent: {tx_hash.hex()}")
            
            
            print("Waiting for transaction receipt...")
            tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
            contract_address = tx_receipt.contractAddress
            print(f"Contract deployed at: {contract_address}")
            
           
            with open("contract_address.txt", "w") as f:
                 f.write(contract_address)
            
            
            contract = w3.eth.contract(address=contract_address, abi=abi)
            return w3, contract
            
        except Exception as e:
            print(f"Deployment error: {e}")
            return None, None
            
    except Exception as e:
        print(f"Compilation error: {e}")
        return None, None


def initialize():
    print("Initializing application...")
    
    CONTRACT_ADDRESS_FILE = os.path.abspath("contract_address.txt")
    ABI_FILE = os.path.abspath("less.json")
    
    if os.path.exists(CONTRACT_ADDRESS_FILE) and os.path.exists(ABI_FILE):
        try:
            
            with open(CONTRACT_ADDRESS_FILE, "r") as f:
                contract_address = f.read().strip()
            with open(ABI_FILE, "r") as f:
                contract_abi = json.load(f)

            print(f"Found existing contract at: {contract_address}")

            
            w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:8545"))
            w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
            if not w3.is_connected():
                print("Error: Cannot connect to blockchain node.")
                return None, None

            w3.eth.default_account = w3.eth.accounts[0]
            contract_address = Web3.to_checksum_address(contract_address)
            contract = w3.eth.contract(address=contract_address, abi=contract_abi)

            
            try:
                dummy_call = contract.functions.userExists("test_user").call()
                print(f"Contract verification successful")
                return w3, contract
            except Exception as e:
                print(f"Contract verification failed: {e}")
                print("Deploying new contract...")
                return compile_and_deploy_contract()

        except Exception as e:
            print(f"Error loading existing contract: {e}")
            return compile_and_deploy_contract()
    else:
        print("No existing contract found. Deploying new contract...")
        return compile_and_deploy_contract()
w3, contract = initialize()



@app.route('/register', methods=['POST'])
def register():
    
    if not w3 or not w3.is_connected():
        return jsonify({
            "status": "error",
            "message": "Not connected to blockchain"
        }), 500
    
    
    

    

    if not contract:
        return jsonify({
            "status": "error",
            "message": "Contract not available"
        }), 500
        
    

    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No data provided"}), 400

        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            return jsonify({"status": "error", "message": "Username and password required"}), 400

        
        try:
            user_exists = contract.functions.userExists(username).call()
            if user_exists:
                return jsonify({"status": "error", "message": "Username already taken"}), 400
        except Exception as e:
            print(f"Error checking if user exists: {e}")
            return jsonify({"status": "error", "message": f"Error checking username: {str(e)}"}), 500

        
        try:
            account = w3.eth.default_account
            nonce = w3.eth.get_transaction_count(account)

            tx = contract.functions.registerUser(username, password).build_transaction({
                'from': account,
                'nonce': nonce,
                'gas': 200000,
                'gasPrice': w3.eth.gas_price
            })

            
            tx_hash = w3.eth.send_transaction(tx)
            print(f"Registration transaction sent: {tx_hash.hex()}")

            
            tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

            if tx_receipt.status == 1:
                return jsonify({"status": "success", "message": "User registered successfully",
                                "transaction_hash": tx_receipt.transactionHash.hex()}), 201
            else:
                return jsonify({"status": "error", "message": "Registration transaction failed"}), 500

        except Exception as e:
            print(f"Error during registration: {e}")
            return jsonify({"status": "error", "message": f"Registration error: {str(e)}"}), 500

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/login-simple', methods=['POST'])
def login_simple():
    
    if not w3 or not contract:
        return jsonify({
            "status": "error",
            "message": "Blockchain or contract not available"
        }), 500
    
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({'status': 'error', 'message': 'Username and password required'}), 400
        
        
        user_exists = contract.functions.userExists(username).call()
        if not user_exists:
            return jsonify({'status': 'error', 'message': 'User not found'}), 401
        
        
        login_success = contract.functions.login(username, password).call()
        
        if login_success:
            
            
            return jsonify({'status': 'success', 'message': 'Login successful'}), 200
        else:
            return jsonify({'status': 'error', 'message': 'Incorrect password'}), 401
            
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
    
@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        
        if 'photo' not in request.files:
            return jsonify({
                "message": "No photo file uploaded",
                "status": "error"
            }), 400
            
        
        photo = request.files['photo']
        patient_username = request.form.get("username")  
        doctor_username = request.form.get("doctorname")  
        description = request.form.get("description")
        document_name = request.form.get("documentName")
        
        
        if not patient_username or not doctor_username or not description or not document_name or not photo:
            return jsonify({
                "message": "All fields must be filled",
                "status": "error"
            }), 400
        
        
        doctor_exists = contract.functions.userExists(doctor_username).call()
        if not doctor_exists:
            return jsonify({'status': 'error', 'message': 'Doctor not found'}), 404
        
        
        photo_file = {
            "file": (secure_filename(photo.filename), photo.stream, photo.mimetype)
        }
        headers = {
            "pinata_api_key": pinata_api,
            "pinata_secret_api_key": pinata_secret
        }
        photo_response = requests.post(pinata_url, files=photo_file, headers=headers)
        if photo_response.status_code != 200:
            return jsonify({
                "error": "Failed to upload photo to IPFS",
                "response": photo_response.text
            }), 500
        
        photo_cid = photo_response.json().get("IpfsHash")
        

        tx_hash = contract.functions.addDocument(
            patient_username,  
            document_name,
            photo_cid,
            description,
            doctor_username 
        ).transact()
        
        tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        
        
        return jsonify({
            "status": "success",
            "message": "Document uploaded successfully",
            "data": {
                "patientUsername": patient_username,
                "documentName": document_name,
                "doctorUsername": doctor_username,
                "photoCid": photo_cid,
                "txHash": tx_hash.hex()
            }
        }), 200
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Server error: {str(e)}"
        }), 500

@app.route('/documents/<username>', methods=['GET'])
def get_documents(username):
    try:
        
        try:
            documents = contract.functions.getDocuments(username).call()
        except Exception as contract_error:
            
            print(f"Contract error: {str(contract_error)}")
            return jsonify({
                'status': 'success',
                'username': username,
                'documentCount': 0,
                'documents': [],
                'message': 'No documents found for this username'
            }), 200
        
        
        documents_formatted = []
        for doc in documents:
            documents_formatted.append({
                'documentName': doc[0],
                
                'description': doc[2],
                'doctorName': doc[3],  
                'fileUrl': f"https://ipfs.io/ipfs/{doc[1]}" 
            })
        
        return jsonify({
            'status': 'success',
            'username': username,
            'documentCount': len(documents),
            'documents': documents_formatted
        }), 200
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({
            'status': "error",
            'message': f'Server error: {str(e)}'
        }), 500
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({
            'status': "error",
            'message': f'Server error: {str(e)}'
        }), 500
        

@app.route('/trigger', methods=['POST'])
def get_response():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No data provided"}), 400
        username = data.get("username")
        doctorname = data.get("doctorname")
        emg_status = data.get("emg_status")
        phone_number_1 = data.get("phone_number_1")
        phone_number_2 = data.get("phone_number_2")
        
        result = main_send_message(
            username=username,
            doctor_name=doctorname,
            emg_status=emg_status,
            phone_number_1=phone_number_1,
            phone_number_2=phone_number_2
        )
        
        
        
        
        print("Final Response:", result)

        
        patient_toggle_url = "http://127.0.0.1:5000/toggle"
        toggle_data = {
            "username": username,
            "doctor_name": doctorname,
            "hasAccess": True  
        }
        try:
            toggle_response = requests.post(patient_toggle_url, json=toggle_data)
            toggle_response.raise_for_status() 
            print("Toggle endpoint response:", toggle_response.json())
        except requests.exceptions.RequestException as e:
            print(f"Error triggering toggle endpoint: {e}")
            
    except Exception as e:
        print(f"Error in trigger endpoint: {e}")
        return jsonify({"status": "error", "message": "Internal server error"}), 500
            






@app.route('/')
def home():
    return "SMS Authorization Service"

@app.route('/send_auth_request', methods=['POST'])
def send_auth_request():
   
    data = {
        "username": request.json.get("username", "John Doe"),
        "doctor_name": request.json.get("doctor_name", "Dr. Smith"),
        "hasAccess": False,
        "sent_time": datetime.utcnow().isoformat(),
        "emg_status": request.json.get("emg_status", True),
        "confirmed": False,  
        "response_received": False 
    }
    
    # Generate unique request ID
    request_id = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    request_data[request_id] = data
    auth_completed[request_id] = False
    
    # Create authorization URL
    auth_url = url_for('authorization_page', request_id=request_id, _external=True)
    
   
    try:
        phone_number_1 = request.json.get('phone_number_1')
        phone_number_2 = request.json.get('phone_number_2')
        
        # Send SMS to the first number
        client.messages.create(
            body=f"Authorization request from {data['doctor_name']} for {data['username']}'s medical records. Please click: {auth_url}",
            from_=TWILIO_PHONE_NUMBER,
            to=phone_number_1
        )
        
        # Send SMS to the second number only if emg_status is True
        if data['emg_status'] and phone_number_2:
            client.messages.create(
                body=f"EMERGENCY: Authorization request from {data['doctor_name']} for {data['username']}'s medical records. Please click: {auth_url}",
                from_=TWILIO_PHONE_NUMBER,
                to=phone_number_2
            )
        
        
        timeout = request.json.get('timeout', 120)  
        start_time = time.time()
        while not auth_completed[request_id] and time.time() - start_time < timeout:
            time.sleep(1) 
        
        
        if not auth_completed[request_id]:
            
            del request_data[request_id]
            del auth_completed[request_id]
            return jsonify({
                "status": "timeout",
                "message": "Request timed out, no response received",
                "username": data['username'],
                "doctor_name": data['doctor_name'],
                "hasAccess": False,
                "emg_status": data['emg_status'],
                "phone_number_1": phone_number_1,
                "phone_number_2": phone_number_2 if data['emg_status'] and phone_number_2 else None
            }), 408
        
       
        final_data = request_data[request_id]
        response = {
            "status": "completed",
            "username": final_data['username'],
            "doctor_name": final_data['doctor_name'],
            "hasAccess": final_data['hasAccess'],
            "emg_status": final_data['emg_status'],
            "phone_number_1": phone_number_1,
            "phone_number_2": phone_number_2 if data['emg_status'] and phone_number_2 else None
        }
        
        
        del request_data[request_id]
        del auth_completed[request_id]
        
        return jsonify(response)
        
    except Exception as e:
        if request_id in request_data:
            del request_data[request_id]
        if request_id in auth_completed:
            del auth_completed[request_id]
        return jsonify({
            "status": "error", 
            "message": str(e),
            "username": data['username'],
            "doctor_name": data['doctor_name'],
            "hasAccess": False,
            "emg_status": data['emg_status'],
            "phone_number_1": request.json.get('phone_number_1'),
            "phone_number_2": request.json.get('phone_number_2')
        }), 400
        
        
@app.route('/authorization/<request_id>')
def authorization_page(request_id):
    
    if request_id not in request_data:
        return "Invalid request"
    
    data = request_data[request_id]
    return render_template('authorization.html', 
                         request_id=request_id,
                         username=data['username'],
                         doctor_name=data['doctor_name'])

@app.route('/process_authorization/<request_id>', methods=['POST'])
def process_authorization(request_id):
    
    if request_id not in request_data:
        app.logger.error(f"Invalid request: {request_id} not found in request_data. Available IDs: {list(request_data.keys())}")
        return jsonify({"error": "Invalid request", "details": "Request not found or expired"})
    
    data = request_data[request_id]
    app.logger.info(f"Processing authorization for request_id: {request_id}")
    
    
    if data['confirmed']:
        return jsonify({"error": "Access has already been granted"})
    
    action = request.form.get('action')
    app.logger.info(f"Action received: {action}")
    
    if action == 'confirm':
        data['hasAccess'] = True
        data['confirmed'] = True  
    
    data['response_received'] = True
    auth_completed[request_id] = True
    
    response = {
        "username": data['username'],
        "doctor_name": data['doctor_name'],
        "hasAccess": data['hasAccess']
    }
    
    return jsonify(response)





    
    
if __name__ == '__main__':
    app.run(debug=True, port=3535)
