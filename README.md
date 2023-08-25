# reservator

Thanks to `howardbp/reservator`. Made config JSON-able, and a few other changes. Note that the api_key in the headers is not a secret, it's a public API key that resy uses on its website.

## Populating Config.json
Put in your email and password for resy.

For `venue_id`, you can go to the place you'd like to visit on resy.com, and go to the `Network` tab of the developer console in Chrome. You'll see a `venue_id` referenced in many of the requests; use this.
