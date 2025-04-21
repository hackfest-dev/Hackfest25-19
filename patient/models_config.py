from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
import os
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GITHUB_API_KEY = os.getenv("GITHUB_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")

def models_configs(model_provider: str, model_name: str, temperature: float = 0.0):
    """
    Function to create a model instance based on the provided model name.
    """
    # Clean and normalize model_provider - handle any comments that might be included
    provider = model_provider.split("#")[0].strip().lower()
    
    if provider == "groq":
        return ChatGroq(temperature=temperature, model=model_name, api_key=GROQ_API_KEY)
    elif provider == "gemini":
        return ChatGoogleGenerativeAI(temperature=temperature, model=model_name, api_key=GEMINI_API_KEY)
    elif provider == "github":
        return ChatOpenAI(temperature=temperature, model=model_name, api_key=GITHUB_API_KEY, base_url=AZURE_OPENAI_ENDPOINT)
    elif provider == "ollama":
        return ChatOllama(temperature=temperature, model=model_name,base_url="http://localhost:11434/v1")
    else:
        raise ValueError(f"Model provider '{provider}' is not supported. Use one of: groq, gemini, github")