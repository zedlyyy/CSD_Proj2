import sys
import json
import requests
import os
import geoip2.database
from geoip2.errors import AddressNotFoundError
import random

notExit = []

with open("Project2ClientInput.json", "r") as f:
    clientData = json.load(f)

alliances = clientData["Alliances"]
client_ip = clientData["Client"]

dest_ip = clientData["Destination"]


with open("tor_consensus.json","r") as f:
    relaysData = json.load(f) 
 

output_file = "tor_consensus_withCountries.json"


#--------------------------GET LOCATION-----------------
DB_PATH = r'.\GeoLite2-Country.mmdb'
reader = geoip2.database.Reader(DB_PATH)

def fallback_ipapi(ip):
    try:
        response = requests.get(f"http://ip-api.com/json/{ip}", timeout=3)
        data = response.json()
        if data.get("status") == "success":
            return data.get("countryCode")
        else:
            print(f"IP-API failed for {ip}: {data.get('message')}")
    except Exception as e:
        return None

def ip_to_country(ip):
    try:
        response = reader.country(ip)
        if response.country.iso_code:
            return response.country.iso_code
        elif response.registered_country.iso_code:
            return response.registered_country.iso_code
        else:
            return None
    except AddressNotFoundError:
        return fallback_ipapi(ip)
    except Exception as e:
        print(f"Failed to get country for IP {ip}: {e}")
        return None
    

def populateAllCountries():
    for data in relaysData:
        ip = data.get("ip")
        country = ip_to_country(ip)
        if country is None:
            print("None recieved")
        data['country'] = country
    with open("tor_consensus_withCountries.json", "w") as f:
        json.dump(relaysData, f, indent=4)


if os.path.exists(output_file):
    with open(output_file, "r") as f:
        relaysData = json.load(f)
else:
    populateAllCountries()


client_location = ip_to_country(client_ip)
dest_location = ip_to_country(dest_ip)



#-------------------------------------- main logic of path -------------------------------------


#Are two countries in the same alliance
def is_in_alliance(country_a, country_b):
    for group in alliances:
        countries = group.get("countries", [])
        if country_a in countries and country_b in countries:
            return True
    return False


def get_country_trust(country):
    trust_values = []
    for alliance in alliances:
        if country in alliance['countries']:
            trust_values.append(alliance['trust'])
    return min(trust_values) if trust_values else 1.0

#---------------------------------------------Guard Logic ------------------------------------------

def guard_security(client_loc, guards):
    for guard in guards:
        guard_country = guard.get('country')
        if not guard_country:
            guard['score'] = 0.0
            continue
        guard_trust = get_country_trust(guard_country)
        if guard_country == client_location:
            guard_trust *= 0.5

        in_alliance = is_in_alliance(client_loc, guard_country)
        if in_alliance:
            guard_trust *= 0.2

        guard['score'] = guard_trust

    return guards

#--------------------------------Exit Logic----------------------
#! Because input.json has no port, we ignore the port here
def canExit(ip, node):
    rules = node.get('exit') 
    rules_arr = rules.split(', ')
    for rule in rules_arr:
        parts = rule.split(" ")
        isAccept = parts[0] == "accept"
        ip_part = parts[1].split(':')[0]
        if isAccept:
            if ip_part == '*' or ip_part == ip:
                return True 
            continue
        else:
            if '*:*' in rule or ip_part == ip:
                return False 
            continue
def populateExitList(relays):
    exitList = []
    for relay in relays:
        rules = relay.get('exit') 
        rules_arr = rules.split(', ')
        if "reject *:*" in rules_arr[0]:
            continue
        exitList.append(relay)
    return exitList

def exit_security(client_loc, dest_loc, guard, exit):
    guardFingerprint = guard.get("fingerprint")
    exitFingerprint = exit.get("fingerprint")
    guard_country = guard.get("country")
    exit_country = exit.get("country")
    # guard must be different than exit
    if guardFingerprint is exitFingerprint:
        return None
    # guard and exit cant be in the same family
    if guardFingerprint in exit.get("family", []) or exitFingerprint in guard.get("family", []):
        return None
    # guard and exit cant be in the same country
    if guard_country == exit_country:
        return None
    # guard and exit must not be in the same alliance
    if is_in_alliance(guard_country, exit_country):
        return None
    

    score = 0
    if exit_country != client_loc:
        score += 1
    score = score * get_country_trust(exit_country)
    if score == 0:
        return None
    return score


#----------------------------------- middle -------------------------------------------------
import random

def select_middle(guard, exit):
    guard_country = guard.get("country")
    exit_country = exit.get("country")
    candidates = []
    for relay in relaysData:
        relay_country = relay.get("country")
        if (relay_country != guard_country and
            relay_country != exit_country):
            candidates.append(relay)
    if not candidates:
        return None
    return random.choice(candidates)






def select_path(in_guards, in_exit):
    GUARD_PARAMS = {         
        "safe_upper": 0.95 ,
        "safe_lower": 2.0 ,      
        "accept_upper": 0.5 ,         
        "accept_lower": 5.0 ,       
        "bandwidth_frac": 0.2
    }

    EXIT_PARAMS = {
        "safe_upper": 0.95 ,         
        "safe_lower": 2.0 ,        
        "accept_upper": 0.1 ,         
        "accept_lower": 10.0 ,        
        "bandwidth_frac": 0.2
    }
    #----------------------------------------- Guard Params --------------------------------------
    guards = sorted(in_guards, key=lambda g: g.get('score', 0), reverse=True) # SORT THEM

    total_bandwidth =  sum(relay['bandwidth']['average'] for relay in relaysData if 'bandwidth' in relay)
    desired_bandwidth = GUARD_PARAMS["bandwidth_frac"] * total_bandwidth

    n = len(guards) 
    max_trust_score = guards[0]["score"] # get Max to get s*

    safeGuards = [] # S
    acceptableGuards = []
    # weight will be used with bandwidth, not here yet
    
    w = 0 # gonna use newtork as the weight 
    index = 0
    while (index < n and 
        guards[index]["score"] >= GUARD_PARAMS["safe_upper"] * max_trust_score and  
        1 - guards[index]["score"] <= GUARD_PARAMS["safe_lower"] * (1 - max_trust_score) and 
        w < desired_bandwidth):
        safeGuards.append(guards[index])
        w = w + guards[index]['bandwidth']['average']
        index += 1  
    while (index < n and 
        guards[index]["score"] >= GUARD_PARAMS["accept_upper"] * max_trust_score and  
        1 - guards[index]["score"] <= GUARD_PARAMS["accept_lower"] * (1 - max_trust_score) and
        w < desired_bandwidth):
        acceptableGuards.append(guards[index])
        w = w + guards[index]['bandwidth']['average']        
        index += 1
        
    if len(safeGuards) == 0 and len(acceptableGuards) == 0:
            return None
        
    #Reorder 
    safeGuards = sorted(safeGuards, key=lambda g: (g.get('score', 0), g.get('bandwidth', {}).get('average', 0)),reverse=True)
    acceptableGuards = sorted(acceptableGuards, key=lambda g: (g.get('score', 0), g.get('bandwidth', {}).get('average', 0)),reverse=True)
    FinalGuard = None
    FinalMiddle = None
    FinalExit = None
    isFinished = False
    for i in range(2):
        loopingGuard = safeGuards
        if i == 1:
            loopingGuard = acceptableGuards
        for safeGuard in loopingGuard:
            exits = []
            for exit in in_exit:
                result =  exit_security(client_location, dest_location , safeGuard, exit)
                if result is None:
                    continue
                exit["score"] = result
                exits.append(exit)


            if len(exits) == 0:
                continue


            exits = sorted(exits, key=lambda g: g.get('score', 0), reverse=True) 
            max_trust_score = exits[0]["score"]
            
            w = 0 # gonna use newtork as the weight 
            index = 0
            safeExits = [] # S
            acceptableExits = []
            n = len(exits) 

            while (index < n and 
                exits[index]["score"] >= EXIT_PARAMS["safe_upper"] * max_trust_score and  
                1 - exits[index]["score"] <= EXIT_PARAMS["safe_lower"] * (1 - max_trust_score) and
                w < desired_bandwidth):

                safeExits.append(exits[index])
                w = w + exits[index]['bandwidth']['average']
                index += 1

            while (index < n and 
                exits[index]["score"] >= EXIT_PARAMS["accept_upper"] * max_trust_score and  
                1 - exits[index]["score"] <= EXIT_PARAMS["accept_lower"] * (1 - max_trust_score) and
                w < desired_bandwidth):

                acceptableExits.append(exits[index])
                w = w + exits[index]['bandwidth']['average']        
                index += 1

            if len(acceptableExits) == 0 and len(safeExits) == 0:
                continue

            availableExits = safeExits
            if len(safeExits) == 0: 
                availableExits = acceptableExits
            
            availableExits = sorted(availableExits, key=lambda g: (g.get('score', 0), g.get('bandwidth', {}).get('average', 0)),reverse=True)

            for availableExit in availableExits:
                FinalMiddle = select_middle(safeGuard, availableExit)
                if FinalMiddle is None:
                    continue
                FinalExit = availableExit
                break
            if FinalMiddle is None:
                continue       
            FinalGuard = safeGuard
            isFinished = True
            break

        if isFinished:
            break


        
    if FinalMiddle is None or FinalExit is None or FinalGuard is None:
            return None

    path = []
    path.append(FinalGuard)
    path.append(FinalMiddle)
    path.append(FinalExit)
    return path

                            

    
 

#----------------------------------- Main Code -----------------------------------------

#! optimization remove at the biggining all the fit exits not possible to get a score as, it depends on the guard
exitList = populateExitList(relaysData)
guardList = guard_security(client_location, relaysData)
result = select_path(guardList, exitList)
if result is None:
    print("No path found")
else:
    for relay in result:
        print(relay.get("country"))

output_path = "output.json"
if result is None:
    print("No path found")
    data_to_save = {"path": None}
else:

    FinalGuard = result[0]
    FinalMiddle = result[1]
    FinalExit = result[2]
    path = [{"guard": FinalGuard}, {"middle": FinalMiddle}, {"exit":FinalExit}]
    data_to_save = {"path": path}

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(data_to_save, f, indent=4)

# guard and exit cant be in a alliance or in the same country
# guard and exit cant be on the same family
# choose middle with the biggest bandwith without being in the same family/Country


# 20% of total bandwidth
# 
