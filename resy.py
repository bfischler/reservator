import requests
import datetime
import time
import csv
import json
import sys

headers = {
     'origin': 'https://resy.com',
     'accept-encoding': 'gzip, deflate, br',
     'x-origin': 'https://resy.com',
     'accept-language': 'en-US,en;q=0.9',
     'authorization': 'ResyAPI api_key="VbWk7s3L4KiK5fzlO7JD3Q5EYolJI7n5"',
     'content-type': 'application/x-www-form-urlencoded',
     'accept': 'application/json, text/plain, */*',
     'referer': 'https://resy.com/',
     'authority': 'api.resy.com',
     'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.102 Safari/537.36',
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

def find_table(res_date, party_size, table_time, auth_token, venue_id):
    #convert datetime to string
    day = res_date.strftime('%Y-%m-%d')
    params = (
     ('x-resy-auth-token',  auth_token),
     ('day', day),
     ('lat', '0'),
     ('long', '0'),
     ('party_size', str(party_size)),
     ('venue_id',str(venue_id)),
    )
    response = requests.get('https://api.resy.com/4/find', headers=headers, params=params)
    data = response.json()
    results = data['results']
    if len(results['venues']) > 0:
        open_slots = results['venues'][0]['slots']
        if len(open_slots) > 0:
            available_times = [(k['date']['start'],datetime.datetime.strptime(k['date']['start'],"%Y-%m-%d %H:%M:00").hour) for k in open_slots]
            closest_time = min(available_times, key=lambda x:abs(x[1]-table_time))[0]

            best_table = [k for k in open_slots if k['date']['start'] == closest_time][0]

            return best_table

def make_reservation(auth_token, config_id, res_date, party_size, payment_method_string):
    #convert datetime to string
    day = res_date.strftime('%Y-%m-%d')
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
    return response


def try_table(day, party_size, table_time, auth_token, restaurant, payment_method_string):
    best_table = find_table(day, party_size, table_time, auth_token, restaurant)
    if best_table is not None:
        hour = datetime.datetime.strptime(best_table['date']['start'],"%Y-%m-%d %H:%M:00").hour
        if hour >= table_time - 2 and hour <= table_time + 2:
            config_id = best_table['config']['token']
            make_reservation(auth_token, config_id, day, party_size, payment_method_string)
            return 1
        else:
            print(f"table found, but not within time range, found at {hour}")
            return 0
    else:
        print("no table found")
        return 0



def main():
    json_config = {}
    with open('./config.json') as c:
        json_config = json.load(c)

    print('logging in')
    auth_token, payment_method_string = login(json_config['email'], json_config['password'])
    print('logged in succesfully')

    party_size = json_config['party_size']
    table_time = json_config['hour']
    dates = json_config['dates']

    venue_id = json_config['venue_id']

    reserved = 0
    while reserved == 0:
        try:
            for date in dates:
                day = datetime.datetime.strptime(date, '%m/%d/%Y')
                reserved = try_table(day, party_size, table_time, auth_token, venue_id, payment_method_string)

                if reserved:
                    print("reservation successful")
                    sys.exit(0)
                else:
                    print("unable to make reservation")
                    time.sleep(.1)

        except Exception as e:
            with open('failures.csv','a') as outf:
                writer = csv.writer(outf)
                writer.writerow([time.time()])

if __name__ == "__main__":
    main()
