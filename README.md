traidor - mtgox command driven terminal trading

CAVEAT
------

this software might have bugs which might cause you to loose money. USE AT
YOUR OWN RISK!

the code is very much a work in progress, if you expect production quality code or even just good code, GO AWAY

DEPENDENCIES (likely incomplete)
--------------------------------

 * simplejson
 * pygame (four sound)
 * websocket4 (included, I guess)
 * ...

LICENSE
-------

probably some GPL license

GETTING STARTED
---------------

First generate a MtGox API Key for use by traidor: go to http://mtgox.com, log in, click your username at the top, select "access" and use "Advanced API Key Creation". Enter any name for the API key (e.g: "traidor"), Check boxes "get_info" and "trade". You will need the "key" and "secret" values for the config file

```
#> cp traidor.conf.sample traidor.conf
#> edit traidor.conf
#> python traidor.py
...
INITIALIZED | 0.0033 dmz | 4.00 BTC, 16.80 USD | [h]elp #> h
```

THANKS
------

* to at least 3 people I forgot the aliases of for testing and suggestions
* to Giel for his websocket implementation
* to MagicalTux for constantly fixing things
