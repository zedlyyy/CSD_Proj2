from ip2geotools.databases.noncommercial import DbIpCity
import json
import requests

def guard_security (client_loc, guards):
    print("nothing")

def exit_security (client_loc, dest_loc, guard, exit):
    print("nothing")

def ip_to_location(ip):
    try:
        response = requests.get(f"https://ipinfo.io/{ip}/json")
        data = response.json()
        return data.get("country") 
    except Exception as e:
        return None

with open("Project2ClientInput.json", "r") as f:
    clientData = json.load(f)

with open("tor_consensus.json","r") as f:
    relaysData = json.load(f) 

print(ip_to_location("178.254.37.2"))
