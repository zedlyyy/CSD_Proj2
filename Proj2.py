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

#Exit or not
def is_possible_exit(relay):
    exit_policy = relay.get('exit', '').lower()
    return 'accept' in exit_policy and 'reject *:*' not in exit_policy

#Are two countries in the same alliance
def is_in_alliance(country_a, country_b, alliances):
    for group in alliances:
        if country_a in group and country_b in group:
            return True
    return False

with open("Project2ClientInput.json", "r") as f:
    clientData = json.load(f)

with open("tor_consensus.json","r") as f:
    relaysData = json.load(f) 

alliances = clientData["Alliances"]
client_ip = clientData["Client"]
dest_ip = clientData["Destination"]

