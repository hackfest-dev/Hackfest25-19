import requests

reponse = requests.get("https://ipfs.io/ipfs/QmbuKEePHecoM3PdWXP2DB5MEJCEBV7jNA311VBdLVZmS6")
print(reponse.json())
