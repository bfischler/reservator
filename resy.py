import requests
import datetime
import time
import csv
import json
import sys
import pause


headers = {}
with open("./headers.json") as f:
    headers = json.load(f)

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
    #  ('x-resy-auth-token',  auth_token),
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
        # TODO: should probably make "interval hours prior" and "interval hours after" configurable
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

    # If you know when the reservation will be released...
    # TODO: should probably turn configurable/a CLI option...
    # pause.until(datetime.datetime(2022, 4, 19, 10, 47, 0))

    reserved = 0
    while reserved == 0:
        try:
            for date in dates:
                day = datetime.datetime.strptime(date, '%m/%d/%Y')
                print(f"checking for {date} at {table_time}...")
                reserved = try_table(day, party_size, table_time, auth_token, venue_id, payment_method_string)
                print(reserved)

                if reserved:
                    print("reservation successful")
                    sys.exit(0)
                else:
                    print("unable to make reservation")
                    time.sleep(.1)

        except Exception as e:
            with open('failures.csv','a') as outf:
                writer = csv.writer(outf)
                writer.writerow([time.time(), str(e)])

if __name__ == "__main__":
    main()
