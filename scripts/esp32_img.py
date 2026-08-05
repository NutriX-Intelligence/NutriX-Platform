import requests

url = "http://192.168.29.134/capture"

response = requests.get(url)

with open("esp32.jpg", "wb") as f:
    f.write(response.content)

print("Image saved.")