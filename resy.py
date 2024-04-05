import requests
import datetime
import time
import csv
import json
import subprocess
import sys


headers = {
     'accept': 'application/json, text/plain, */*',
     'accept-encoding': 'gzip, deflate, br',
     'accept-language': 'en-US,en;q=0.9',
     'authorization': 'ResyAPI api_key="VbWk7s3L4KiK5fzlO7JD3Q5EYolJI7n5"',
     'authority': 'api.resy.com',
     'cache-control': 'no-cache',
     'content-type': 'application/x-www-form-urlencoded',
     'origin': 'https://resy.com',
     'referer': 'https://resy.com/',
     'sec-ch-ua': '"Google Chrome";v="113", "Chromium";v="113", "Not-A.Brand";v="24"',
     'sec-ch-ua-mobile': '?0',
     'sec-ch-ua-platform': '"macOS"',
     'sec-fetch-dest': 'empty',
     'sec-fetch-mode': 'cors',
     'sec-fetch-site': 'same-site',
     'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
     'x-origin': 'https://resy.com',
}

def login(username, password):
    data = {
      'email': username,
      'password': password
    }

    response = requests.post('https://api.resy.com/3/auth/password', headers=headers, data=data)
    res_data = response.json()
    auth_token = res_data['token']
    payment_method_string = '{"id":' + str(res_data['payment_method_id']) + '}'
    return auth_token, payment_method_string

def find_tables(ideal_time, party_size, auth_token, venue_id):
    day = ideal_time.strftime('%Y-%m-%d')
    curl_cmd = f"""
    curl 'https://api.resy.com/4/find?lat=0&long=0&day={day}&party_size={party_size}&venue_id={venue_id}' \
    -H 'authority: api.resy.com' \
    -H 'accept: application/json, text/plain, */*' \
    -H 'accept-language: en-US,en;q=0.9' \
    -H 'authorization: ResyAPI api_key="VbWk7s3L4KiK5fzlO7JD3Q5EYolJI7n5"' \
    -H 'cache-control: no-cache' \
    -H 'origin: https://resy.com' \
    -H 'referer: https://resy.com/' \
    -H 'sec-ch-ua: "Google Chrome";v="113", "Chromium";v="113", "Not-A.Brand";v="24"' \
    -H 'sec-ch-ua-mobile: ?0' \
    -H 'sec-ch-ua-platform: "macOS"' \
    -H 'sec-fetch-dest: empty' \
    -H 'sec-fetch-mode: cors' \
    -H 'sec-fetch-site: same-site' \
    -H 'user-agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36' \
    -H 'x-origin: https://resy.com' \
    --compressed
    """

    process = subprocess.Popen(curl_cmd, stdout=subprocess.PIPE, shell=True)
    output, error = process.communicate()

    if error:
        print(f"Error occurred: {error}")
        return []

    output_str = output.decode("utf-8")  # decode the byte string to a normal string
    data = json.loads(output_str)  # parse the string as JSON
    results = data['results']
    if len(results['venues']) > 0:
        open_slots = results['venues'][0]['slots']
        return sorted(open_slots, key=lambda x:abs(
            datetime.datetime.strptime(x['date']['start'],"%Y-%m-%d %H:%M:00") - ideal_time))
    return []

def make_reservation(auth_token, config_id, ideal_time, party_size, payment_method_string):
    #convert datetime to string
    day = ideal_time.strftime('%Y-%m-%d')
    party_size = str(party_size)
    params = (
         ('x-resy-auth-token', auth_token),
         ('config_id', str(config_id)),
         ('day', day),
         ('party_size', str(party_size)),
    )
    details_request = requests.get('https://api.resy.com/3/details', headers=headers, params=params)
    details = details_request.json()
    book_token = details['book_token']['value']
    headers['x-resy-auth-token'] = auth_token
    data = {
      'book_token': book_token,
      'struct_payment_method': payment_method_string,
      'source_id': 'resy.com-venue-details'
    }

    response = requests.post('https://api.resy.com/3/book', headers=headers, data=data)
    try:
        res = response.json()
        return res.get("reservation_id")
    except Exception as e:
        print(f"Error making reservation: {e}")
        return None


def try_table(ideal_time, flexibility_minutes_before, flexibility_minutes_after, party_size, auth_token, restaurant, payment_method_string):
    best_tables = find_tables(ideal_time, party_size, auth_token, restaurant)
    if best_tables:
        for best_table in best_tables:
            table_time = datetime.datetime.strptime(best_table['date']['start'], "%Y-%m-%d %H:%M:00")
            time_difference_minutes = (table_time - ideal_time).total_seconds() / 60
            if (
                    (0 <= time_difference_minutes <= flexibility_minutes_after)
                    or (-flexibility_minutes_before <= time_difference_minutes <= 0)):
                config_id = best_table['config']['token']
                reservation_id = make_reservation(auth_token, config_id, ideal_time, party_size, payment_method_string)
                if reservation_id is not None:
                    print(f"Made reservation! ID: {reservation_id}, time: {table_time}")
                    return True
                else:
                    print(f"Failed at booking step ({table_time})")
                    continue
            else:
                print(f"table found, but not within time range, found at {table_time}")
                continue
    else:
        print("no table found")
        return False



def main():
    json_config = {}
    with open('./config.json') as c:
        json_config = json.load(c)

    print('logging in')
    auth_token, payment_method_string = login(json_config['email'], json_config['password'])
    print('logged in succesfully')

    party_size = json_config['party_size']
    datetimes = json_config['datetimes']
    flexibility_minutes_before = json_config.get('flexibility_minutes_before', 0)
    flexibility_minutes_after = json_config.get('flexibility_minutes_after', 0)
    attempt_start_time = json_config.get('attempt_start_time')
    attempt_frequency_seconds = json_config.get('attempt_frequency_seconds', 60)
    runs_per_attempt = json_config.get('runs_per_attempt', 1)
    venue_ids = json_config['venue_ids']

    reserved = False
    time_to_try = (
        datetime.datetime.strptime(attempt_start_time, '%Y-%m-%d %H:%M:%S')
        if attempt_start_time else datetime.datetime.now().replace(
            microsecond=0, second=0, minute=0))
    while True:
        if time_to_try < datetime.datetime.now():
            print("Skipping", time_to_try)
            time_to_try = time_to_try + datetime.timedelta(seconds=attempt_frequency_seconds)
            continue
        print("Waiting until", time_to_try)
        time.sleep((time_to_try - datetime.datetime.now()).total_seconds())
        time_to_try = time_to_try + datetime.timedelta(seconds=attempt_frequency_seconds)
        attempt_number = 0
        while not reserved:
            attempt_number += 1
            if attempt_number > runs_per_attempt:
                break
            print("Attempt", attempt_number)
            try:
                for venue_id in venue_ids:
                    for dt in datetimes:
                        ideal_time = datetime.datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')
                        reserved = try_table(ideal_time, flexibility_minutes_before, flexibility_minutes_after, party_size, auth_token, venue_id, payment_method_string)

                        if reserved:
                            print("reservation successful")
                            return
                        else:
                            print("unable to make reservation")
                            continue

            except Exception as e:
                print(e)
                with open('failures.csv','a') as outf:
                    writer = csv.writer(outf)
                    writer.writerow([time.time()])

if __name__ == "__main__":
    main()
