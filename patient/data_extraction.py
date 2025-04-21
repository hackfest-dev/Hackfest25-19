import os
import json
import io
import base64
import datetime
from time import sleep
from typing import Optional, Dict, Any
from PIL import Image
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq
from models_config import models_configs

# Load environment variables
load_dotenv()

model_provider = os.getenv("MODEL_PROVIDER", "").strip()
temperature = float(os.getenv("TEMPERATURE", 0.0))
model_name = os.getenv("MODEL_NAME", "")

app = Flask(__name__)

# Initialize model
model = models_configs(
    model_provider=model_provider,
    model_name=model_name,
    temperature=temperature
)

# Replace Pydantic models with Python classes
class AadhaarProfile:
    def __init__(self, name="", gender="", dob="", phone_number="", addhar_number="", 
                 issue_date="", son_of="", address="", city="", state="", postal_code=""):
        self.name = name
        self.gender = gender
        self.dob = dob
        self.phone_number = phone_number
        self.addhar_number = addhar_number
        self.issue_date = issue_date
        self.son_of = son_of  # Equivalent to 'Son/of' in the original
        self.address = address
        self.city = city
        self.state = state
        self.postal_code = postal_code
    
    def to_dict(self):
        return {
            "name": self.name,
            "gender": self.gender,
            "dob": self.dob,
            "phone_number": self.phone_number,
            "addhar_number": self.addhar_number,
            "issue_date": self.issue_date,
            "Son/of": self.son_of,
            "address": self.address,
            "city": self.city,
            "state": self.state,
            "postal_code": self.postal_code
        }

class AadhaarResponse:
    def __init__(self, username, profile):
        self.username = username
        self.profile = profile if isinstance(profile, AadhaarProfile) else AadhaarProfile(**profile)
    
    def to_dict(self):
        return {
            "username": self.username,
            "profile": self.profile.to_dict()
        }

def encode_image(file):
    """Encode binary file content to base64 string"""
    return base64.b64encode(file).decode("utf-8")

def encode_image_pil(image: Image.Image) -> str:
    """Encode PIL Image to base64 string"""
    buffered = io.BytesIO()
    image = image.convert("RGB")
    image.save(buffered, format="JPEG", quality=85)
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

def split_image_into_horizontal_stripes(image: Image.Image, stripe_count: int = 5, overlap: float = 0.1):
    """Split an image into horizontal stripes with overlap"""
    width, height = image.size
    stripe_height = height // stripe_count
    overlap_height = int(stripe_height * overlap)

    stripes = []
    for i in range(stripe_count):
        upper = max(i * stripe_height - overlap_height, 0)
        lower = min((i + 1) * stripe_height + overlap_height, height)
        stripe = image.crop((0, upper, width, lower))
        stripes.append(stripe)
    return stripes

def ocr(image: Image.Image) -> str:
    """Extract text from image using OCR"""
    groq_llm = models_configs(
        model_provider=model_provider,
        model_name=model_name,
        temperature=temperature
    )

    image_data_url = f"data:image/jpeg;base64,{encode_image_pil(image)}"

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": (
                    "The uploaded image/medical image/pdf might contains printed text or handwritten notes. "
                    "Your task is to carefully extract all textual content, including handwritten elements.(if there) and then get it detailed"
                )},
                {"type": "image_url", "image_url": {"url": image_data_url}}
            ]
        }
    ]

    response = groq_llm.invoke(messages)
    return response.content.strip()

def format_to_table(markdown_runs: list) -> str:
    """Format extracted text into a structured table"""
    groq_llm = models_configs(
        model_provider=model_provider,
        model_name=model_name,
        temperature=temperature
    )

    combined_markdown = "\n\n".join(markdown_runs)

    messages = [
        {
            "role": "user",
            "content": (
                "You are provided with multiple markdown outputs extracted from overlapping sections of an image."
                "Some sections may contain duplicate or conflicting information due to overlaps. "
                "Your task is to:"
                "\n\n1. Identify and consolidate rows of data that are related, ensuring that the most complete version of the information is retained."
                "\n2. For rows with conflicting information (e.g., different values for a field), prioritize the more detailed entry."
                "\n3. If a field is missing in one row but present in another, combine the information into a single row."
                "\n4. Output the consolidated data in a clean tabular format using Markdown syntax, suitable for direct rendering."
                "\n5. Output Only Markdown: Return solely the Markdown content without any additional explanations or comments."
                "\n6. it should be detailed as possible and not to make any mistake in extracting."
                "\n7. and add a section where it gives the full details of each item in a detailed column."
                "\n9. never refer it as patient always refer it as Your."
                "\n10. make sure that you extract all the data and it should be in row and cloumn format.(Detailed)"
                "\n\nHere is the data to process:\n\n"
                + combined_markdown
            )
        }
    ]

    response = groq_llm.invoke(messages)
    return response.content.strip()

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
        
        # If "profile" is not present, wrap the flat dict as profile
        if "profile" not in data:
            profile_fields = ["name", "gender", "dob", "phone_number", "addhar_number", 
                              "issue_date", "son_of", "address", "city", "state", "postal_code"]
            profile_data = {k: data.get(k, "") for k in profile_fields}
            if "Son/of" in data:
                profile_data["son_of"] = data.get("Son/of", "")
            data = {"username": username, "profile": profile_data}
        
        aadhaar_response = AadhaarResponse(**data)

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
    import requests

    pinata_api_key = os.getenv("PINATA_API_KEY")
    pinata_secret_api_key = os.getenv("PINATA_SECRET_API_KEY")
    pinata_url = "https://api.pinata.cloud/pinning/pinJSONToIPFS"

    headers = {
        "pinata_api_key": pinata_api_key,
        "pinata_secret_api_key": pinata_secret_api_key
    }

    payload = {
        "pinataMetadata": {
            "name": username
        },
        "pinataContent": data
    }

    response = requests.post(pinata_url, json=payload, headers=headers)
    return response.json()

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


