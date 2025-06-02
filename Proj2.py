from ip2geotools.databases.noncommercial import DbIpCity
import json
import requests

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


def get_country_trust(country, alliances):
    trust_values = []
    for alliance in alliances:
        if country in alliance['countries']:
            trust_values.append(alliance['trust'])
    return max(trust_values) if trust_values else 0.0


def guard_security(client_loc, guards):
    scored_guards = []

    #Client Aliances
    client_alliances = [set(a['countries']) for a in alliances if client_loc in a['countries']]

    for guard in guards:
        guard_country = guard.get('country')
        bandwidth = guard.get('bandwidth', {}).get('measured', 0)

        guard_trust = get_country_trust(guard_country, alliances)

        #If guard does is not in alliance with any of the client alliances
        if all(guard_country not in group for group in client_alliances):
            guard_trust *= 0.5

        score = guard_trust * bandwidth
        scored_guards.append((guard, score))

    scored_guards.sort(key=lambda x: x[1], reverse=True)
    return scored_guards


def get_pair_trust(country1, country2):
    best = None
    for alliance in alliances:
        if country1 in alliance["countries"] and country2 in alliance["countries"]:
            if best is None:
                best = alliance["trust"]
            else:
                best = max(best, alliance["trust"])
    return best if best is not None else 0.0

def exit_security(client_loc, dest_loc, guard_country, exit_country):
    entry_countries = {client_loc, guard_country}
    exit_countries = {dest_loc, exit_country}

    worst_risk = 0.0  

    for ec in entry_countries:
        for xc in exit_countries:
            trust = get_pair_trust(ec, xc)
            risk = 1 - trust
            worst_risk = max(worst_risk, risk)

    score = 1 - worst_risk
    return score


def select_path (relays, alpha_params) :
    print("nothing")


with open("Project2ClientInput.json", "r") as f:
    clientData = json.load(f)

with open("tor_consensus.json","r") as f:
    relaysData = json.load(f) 

alliances = clientData["Alliances"]
client_ip = clientData["Client"]
dest_ip = clientData["Destination"]

