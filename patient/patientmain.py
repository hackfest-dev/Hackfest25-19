from flask import Flask, request, jsonify
from web3 import Web3
import json
import os
from web3.middleware import ExtraDataToPOAMiddleware
from solcx import compile_standard, install_solc
PINATA_API_KEY = "c488ba1035d164c4a33c"
PINATA_API_SECRET = "204cfc1828908c7314a4ba9ad283a73402dc0a2854c41777953a1fed5148264d"
PINATA_API_URL = "https://api.pinata.cloud/pinning/pinFileToIPFS"
import requests
from data_extraction import *

from flask_cors import CORS




app = Flask(__name__)
CORS(app)


try:
    install_solc("0.8.0")
    print("Solidity compiler installed successfully")
except Exception as e:
    print(f"Warning: Could not install Solidity compiler: {e}")

with open("s.sol", "r") as f:
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
    """Register a new user"""
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
            return jsonify({"status"
                            : "error", "message": "No data provided"}), 400
            
        username = data.get('username')
        password = data.get('password')
        print(username,password)
            
       
                
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
        print(username,password)
        
        
        
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
def upload_document():
    
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

    data = request.form.get("extractedtext")
    username = request.form.get("username")
    documentname = request.form.get("document")
    extractedtext = json.loads(data) if data else None
    photo = request.files.get("photo")

    
    if not extractedtext or not photo:
        return jsonify({"error": "Missing 'extractedtext' or 'photo' in request"}), 400

    
    extractedtext_file = ("extractedtext.json", json.dumps(extractedtext), "application/json")

    
    photo_file_data = ("photo", photo.stream, photo.mimetype)

    
    headers = {
        "pinata_api_key": PINATA_API_KEY,
        "pinata_secret_api_key": PINATA_API_SECRET
    }

    
    response1 = requests.post(PINATA_API_URL, files={"file": extractedtext_file}, headers=headers)
    if response1.status_code == 200:
        cid1 = response1.json().get("IpfsHash")
    else:
        return jsonify({
            "error": "Failed to upload 'extractedtext' to IPFS",
            "statusCode": response1.status_code,
            "response": response1.text
        }), 500

    
    response2 = requests.post(PINATA_API_URL, files={"file": photo_file_data}, headers=headers)
    if response2.status_code == 200:
        
        cid2 = response2.json().get("IpfsHash")
        
            
    else:
        return jsonify({
            "error": "Failed to upload 'photo' to IPFS",
            "statusCode": response2.status_code,
            "response": response2.text
        }), 500

    
    try:
        if not all([username, documentname, cid1, cid2]):
            return jsonify({
                "status": "error",
                "message": "All fields (username, documentName, photoCid, jsonCid) are required"
            }), 400

        
        user_exists = contract.functions.userExists(username).call()
        if not user_exists:
            return jsonify({"status": "error", "message": "User not found"}), 404

        account = w3.eth.default_account
        nonce = w3.eth.get_transaction_count(account)

        
        tx = contract.functions.addDocument(
            username, documentname, cid2, cid1
        ).build_transaction({
            'from': account,
            'nonce': nonce,
            'gas': 500000,
            'gasPrice': w3.eth.gas_price
        })

        
        tx_hash = w3.eth.send_transaction(tx)
        tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

        if tx_receipt.status == 1:
            return jsonify({
                "status": "success",
                "message": "Document uploaded successfully",
                "documentName": documentname,
                "photoCid": cid2,
                "jsonCid": cid1,
                "username": username
            }), 201
        else:
            return jsonify({"status": "error", "message": "Document upload transaction failed"}), 500

    except Exception as e:
        return jsonify({"status": "error", "message": f"Document upload error: {str(e)}"}), 500

@app.route('/toggle', methods=['POST'])
def toggle_privacy():
    try:
        
        data = request.get_json()
        patientname = data.get('username')
        doctorname = data.get('doctor_name')
        has_access = data.get('hasAccess', False)
        
        print(patientname, doctorname, has_access)

        # Input Validation
        if not patientname or not doctorname:
            return jsonify({"status": "error", "message": "Invalid patientname or doctorname"}), 400
        if not isinstance(has_access, bool):
            return jsonify({"status": "error", "message": "Invalid hasAccess value"}), 400

        print(f"Inputs - Patientname: {patientname}, Doctorname: {doctorname}, HasAccess: {has_access}")

        # Check user existence
        user_exists = contract.functions.userExists(patientname).call()
        if not user_exists:
            return jsonify({"status": "error", "message": "User not found"}), 404

        # Build transaction
        account = w3.eth.default_account
        nonce = w3.eth.get_transaction_count(account)

        print(f"Account: {account}, Nonce: {nonce}")

        tx = contract.functions.toggleDoctorAccess(
            patientname, doctorname, has_access
        ).build_transaction({
            'from': account,
            'nonce': nonce,
            'gas': 500000,
            'gasPrice': w3.eth.gas_price
        })

        # Send transaction
        tx_hash = w3.eth.send_transaction(tx)
        tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        print(tx_hash)

        return jsonify({
            "status": "success",
            "message": f"The {doctorname} has requested access: {has_access}"
        })
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"status": "error", "message": str(e)})


@app.route('/data/<doctorname>/<patientname>', methods=['GET'])
def getdata(patientname, doctorname):
    try:
        # Check access
        has_access = contract.functions.checkAccess(patientname, doctorname).call()
        if not has_access:
            return jsonify({
                'success': False,
                'message': 'Access denied: Doctor does not have permission'
            }), 403

        # Check if user exists
        user_exists = contract.functions.userExists(patientname).call()
        if not user_exists:
            return jsonify({"status": "error", "message": "User not found"}), 404

        
        documents = contract.functions.getDocuments(patientname).call()
        result = {}
        for doc in documents:
            doc_name = doc[0]  
            photo_cid = doc[1]  
            json_cid = doc[2]   
            result[f"{doc_name}photo"] = photo_cid
            result[f"{doc_name}json"] = json_cid
        
        result["username"] = patientname

        return jsonify({
            "status": "success",
            "message": f"Retrieved {len(documents)} documents for user {patientname}",
            "documents": result
        }), 200

    except Exception as e:
        print(f"Error retrieving data: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/get/<username>', methods = ['GET'])
def get(username):
    try:
        
        
        doctor_url =  f"http://127.0.0.1:3535/documents/{username}"
        response = requests.get(doctor_url)
        
        if response.status_code == 200:
            return jsonify( response.json())
        else:
            return jsonify({
                'status': 'error',
                'message': f'Failed to fetch documents: {response.text}'
            }), response.status_code
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Server error: {str(e)}'
        }), 500

        
    
    
    
    
        



        

notifications = []
@app.route('/notify', methods=['POST'])
def notify():
    try:
        
        data = request.get_json()
        username = data.get('username')
        message = data.get('messege')

        
        if not all([username, message]):
            return jsonify({'error': 'Missing required fields: username and message'}), 400

        
        notifications.append({
            'username': username,
            'message': message
        })

        return jsonify({'message': 'Notification received successfully'}), 200

    except Exception as e:
        return jsonify({'error': f'Failed to process notification: {str(e)}'}), 500

@app.route('/notify/<username>', methods=['GET'])
def get_notifications(username):
    try:
        
        matching_notifications = [
            notif for notif in notifications
            if notif['username'] == username
        ]

        if not matching_notifications:
            return jsonify({
                'message': f'No notifications found for username {username}',
                'notifications': []
            }), 404

        return jsonify({
            'message': f'Notifications retrieved for username {username}',
            'notifications': matching_notifications
        }), 200
    except Exception as e:
        return jsonify({'error': f'Failed to retrieve notifications: {str(e)}'}), 500
    
    

@app.route('/api/usernames', methods=['GET'])
def get_all_usernames():
    try:
        
        usernames = contract.functions.getRegisteredUsers().call()
        
       
        username_list = []
        for username in usernames:
            username_list.append(username)
        
        return jsonify({
            'success': True,
            'usernames': username_list,
            'count': len(username_list)
        })
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(error_details) 
        
        return jsonify({
            'success': False,
            'error': str(e),
            'details': error_details
        }), 500
        
        
@app.route('/dae/<patientname>', methods=['GET'])
def get_data(username):
    try:
        user_exists = contract.functions.userExists(username).call()
        if not user_exists:
            return jsonify({"status": "error", "message": "User not found"}), 404

        
        documents = contract.functions.getphonenumbers(username).call()
        result = {}
        for doc in documents:
            doc_name = doc[0]  
            photo_cid = doc[1]  
            
            result["doc_name"] = doc_name
            result["json"] = photo_cid
            result["username"] = username

        

    except Exception as e:
        print(f"Error retrieving data: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    

@app.route("/upload-image/", methods=["POST"])
def upload_image():
    """Endpoint to extract Aadhaar card information and upload to Pinata"""
    try:
        # Get username from request parameters
        username = request.form.get("username")
        if not username:
            return jsonify({"error": "Username is required"}), 400
            
        # Check if file exists in request
        if 'file' not in request.files:
            return jsonify({"error": "No file part in the request"}), 400
            
        file = request.files['file']
        
        # Check if filename is empty
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        # Read file content
        file_content = file.read()
        base64_image = encode_image(file_content)
        
        # Generate the expected JSON format using the class
        format_dict = AadhaarResponse(
            username=username,
            profile=AadhaarProfile()
        ).to_dict()
        json_format_str = json.dumps(format_dict, indent=4)

        # Prepare message for the model with clear instructions
        message = HumanMessage(
            content=[
                {"type": "text", "text": f"""Extract all the information from this Aadhaar card image. Return ONLY a valid JSON object using exactly this format:
{json_format_str}
Do not include any explanation, markdown formatting, or code blocks in your response. Make sure that what username is given to you should be used."""},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                },
            ],
        )

        # Invoke model
        response = model.invoke([message])
        cleaned_response = response.content.replace("```json", "").replace("```", "").strip()

        # Parse the cleaned response using json and validate
        try:
            data = json.loads(cleaned_response)
        except json.JSONDecodeError:
            data = eval(cleaned_response)
        
        # Ensure username is set from the endpoint input
        data["username"] = username
        
        # Map "Son/of" to "son_of" for compatibility with AadhaarProfile
        if "profile" in data and "Son/of" in data["profile"]:
            data["profile"]["son_of"] = data["profile"].pop("Son/of")
        
        aadhaar_response = AadhaarResponse(**data)
        print(aadhaar_response.to_dict())

        # Upload extracted JSON to Pinata
        pinata_response = upload_to_pinata(username, aadhaar_response.to_dict())
        if not pinata_response.get("success"):
            return jsonify({"error": "Failed to upload to Pinata"}), 500

        return jsonify({
            "message": "Data successfully extracted and uploaded to Pinata",
            "pinata_response": pinata_response
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


def upload_to_pinata(username: str, data: dict) -> dict:
    """Upload extracted data to Pinata"""
    try:
        import requests
        
        pinata_api_key = PINATA_API_KEY
        pinata_secret_api_key = PINATA_API_SECRET
        pinata_url = "https://api.pinata.cloud/pinning/pinJSONToIPFS"

        # Update headers with correct format
        headers = {
            "Content-Type": "application/json",
            "pinata_api_key": pinata_api_key,
            "pinata_secret_api_key": pinata_secret_api_key
        }

        # Add metadata with more details
        payload = {
            "pinataOptions": {
                "cidVersion": 1
            },
            "pinataMetadata": {
                "name": f"aadhaar_data_{username}",
                "keyvalues": {
                    "username": username,
                    "type": "aadhaar_data"
                }
            },
            "pinataContent": data
        }

        response = requests.post(
            pinata_url,
            json=payload,
            headers=headers,
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"Pinata Error: {response.text}")
            return {
                "success": False,
                "error": f"Pinata API error: {response.status_code}"
            }

        response_data = response.json()
        cid1 = response_data.get("IpfsHash")
        user_exists = contract.functions.userExists(username).call()
        if not user_exists:
            return jsonify({"status": "error", "message": "User not found"}), 404

        account = w3.eth.default_account
        nonce = w3.eth.get_transaction_count(account)

        
        tx = contract.functions.addphonenumbers(
            username, cid1
        ).build_transaction({
            'from': account,
            'nonce': nonce,
            'gas': 500000,
            'gasPrice': w3.eth.gas_price
        })

        
        tx_hash = w3.eth.send_transaction(tx)
        tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

        if tx_receipt.status == 1:
            return jsonify({
                "status": "success",
                "message": "Document uploaded successfully",
                "username": username,
                "jsonCid": cid1,
                
            }), 201
        else:
            return jsonify({"status": "error", "message": "Document upload transaction failed"}), 500

    except Exception as e:
        return jsonify({"status": "error", "message": f"Document upload error: {str(e)}"}), 500


@app.route("/process-document/", methods=["POST"])
def process_document():
    """Endpoint to process general documents for text extraction"""
    try:
        # Get form data
        name = request.form.get("name")
        document_name = request.form.get("document_name")
        
        if not name or not document_name:
            return jsonify({"error": "Name and document_name are required"}), 400
            
        # Check if file exists in request
        if 'file' not in request.files:
            return jsonify({"error": "No file part in the request"}), 400
            
        file = request.files['file']
        
        # Check if filename is empty
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        # Read and process the uploaded file
        file_content = file.read()
        file_extension = file.filename.split(".")[-1].lower()

        if file_extension not in ["jpg", "jpeg", "png", "pdf"]:
            return jsonify({"error": "Unsupported file type"}), 400

        # Process file based on type
        if file_extension == "pdf":
            from PyPDF2 import PdfReader
            pdf_reader = PdfReader(io.BytesIO(file_content))
            extracted_text = "\n".join(page.extract_text() for page in pdf_reader.pages)
        else:
            image = Image.open(io.BytesIO(file_content))
            extracted_text = ocr(image)

        # Consolidate results into a table
        markdown_runs = [extracted_text]
        table_output = format_to_table(markdown_runs)

        # Get current date for uploaded_date
        current_date = datetime.datetime.now().strftime("%Y-%m-%d")

        # Prepare JSON response
        response_json = {
            "name": name,
            "content_markdown": table_output,
            "document_name": document_name,
            "uploaded_date": current_date,
            "Image_download": file.filename
        }

        return jsonify(response_json)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)