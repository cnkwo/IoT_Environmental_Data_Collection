import network
import socket
import ure
import time
import ucryptolib
from main import ESP32Handler

ap_ssid =  "IEDC-FYP"
ap_password = "73f61fe4f711"
ap_authmode = 3  # WPA2
sender_key = b'\xd9\x02.0\xce\x8a\x1b\x1d\x11\xf7j\x00\x113\xb05\xa4q\xf1cp.\x88t\x81A\xcci\xbb\t\xd0\x0c' #d9022e30ce8a1b1d11f76a001133b035a471f163702e88748141cc69bb09d00c
esphand = ESP32Handler()

NETWORK_PROFILES = 'wifi.dat'

wlan_ap = network.WLAN(network.AP_IF)
wlan_sta = network.WLAN(network.STA_IF)

server_socket = None


def get_connection():
    """return a working WLAN(STA_IF) instance or None"""

    # First check if there already is any connection:
    if wlan_sta.isconnected():
        return wlan_sta

    connected = False
    try:
        # ESP connecting to WiFi takes time, wait a bit and try again:
        time.sleep(3)
        if wlan_sta.isconnected():
            return wlan_sta

        # Read known network profiles from file
        profiles = read_profiles()

        # Search WiFis in range
        wlan_sta.active(True)
        networks = wlan_sta.scan()

        AUTHMODE = {0: "open", 1: "WEP", 2: "WPA-PSK", 3: "WPA2-PSK", 4: "WPA/WPA2-PSK"}
        for ssid, bssid, channel, rssi, authmode, hidden in sorted(networks, key=lambda x: x[3], reverse=True):
            ssid = ssid.decode('utf-8')
            encrypted = authmode > 0
            print("ssid: %s chan: %d rssi: %d authmode: %s" % (ssid, channel, rssi, AUTHMODE.get(authmode, '?')))
            if encrypted:
                if ssid in profiles:
                    password = profiles[ssid]
                    connected = do_connect(ssid, password)
                else:
                    print("skipping unknown encrypted network")
            else:  # open
                connected = do_connect(ssid, None)
            if connected:
                break

    except OSError as e:
        print("exception", str(e))

    # start web server for connection manager:
    if not connected:
        connected = start()

    return wlan_sta if connected else None


def read_profiles():
    with open(NETWORK_PROFILES) as f:
        lines = f.readlines()
    profiles = {}
    for line in lines:
        ssid, password = line.strip("\n").split(";")
        profiles[ssid] = password
    return profiles


def write_profiles(profiles):
    lines = []
    for ssid, password in profiles.items():
        lines.append("%s;%s\n" % (ssid, password))
    with open(NETWORK_PROFILES, "w") as f:
        f.write(''.join(lines))


# ... (existing code)

# XOR-based encryption function
def xor_encrypt_decrypt(data, key):
    return bytes([a ^ b for a, b in zip(data, key)])

# Global variables to store the SSID and password after a successful connection
connected_ssid = None
connected_password = None

def do_connect(ssid, password):
    global connected_ssid, connected_password

    wlan_sta.active(True)
    if wlan_sta.isconnected():
        return None

    # Update popup here
    print('Trying to connect to %s...' % ssid)
    wlan_sta.connect(ssid, password)

    for retry in range(200):
        connected = wlan_sta.isconnected()
        if connected:
            print('\nConnected to Wi-Fi network:')
            esphand.alertUser(alertType = " Alert!", message = "Connected!", displayState = 1, status = 10)
            
            time.sleep(2)
            
            esphand.alertUser(alertType = " Alert!", message = "Connected!", displayState = 0, status = 10)
            #print("SSID:", ssid)
            #print("Password:", password)
            #print("Network config:", wlan_sta.ifconfig())
        
            # Update the global variables with the connected SSID and password
            #cipher = cryptolib.(sender_key, cryptolib.MODE_ECB)
            #connected_ssid = cipher.encrypt(ssid)
            #connected_password = cipher.encrypt(password)
            
            #ssid_bytes = ssid.encode()
            #password_bytes = password.encode()
            
            #connected_ssid = cryptolib.aes(sender_key, ssid_bytes)
            #connected_password = cryptolib.aes(sender_key, password_bytes)
            
            #cipher = AES(sender_key)
            
            #connected_ssid = cipher.encrypt(ssid.encode())
            #connected_password = cipher.encrypt(password.encode())
            
            connected_ssid = xor_encrypt_decrypt(ssid.encode(), sender_key)
            connected_password = xor_encrypt_decrypt(password.encode(), sender_key)

            
            
            break

        time.sleep(0.1)
        print('.', end='')

    if connected:
        return ssid, password
    else:
        # Update popup here!!!
        print('\nFailed. Not Connected to: ' + ssid)
        esphand.alertUser(alertType = " Warning!", message = "No WiFi", displayState = 1, status = 8) 
        return None

# ... (existing code)

def send_header(client, status_code=200, content_length=None ):
    client.sendall("HTTP/1.0 {} OK\r\n".format(status_code))
    client.sendall("Content-Type: text/html\r\n")
    if content_length is not None:
      client.sendall("Content-Length: {}\r\n".format(content_length))
    client.sendall("\r\n")


def send_response(client, payload, status_code=200):
    content_length = len(payload)
    send_header(client, status_code, content_length)
    if content_length > 0:
        client.sendall(payload)
    client.close()


def handle_root(client):
    wlan_sta.active(True)
    ssids = sorted(ssid.decode('utf-8') for ssid, *_ in wlan_sta.scan())
    send_header(client)
    client.sendall("""\
        <html>
        <head>
            <title>Wi-Fi Manager</title>
            <style>
                body {
                  background-color: #e9f5ff;
                  font-family: Arial, sans-serif;
                }
                
                h1 {
                  color: #005cbf;
                }
                
                .container {
                  max-width: 400px;
                  margin: 0 auto;
                  padding: 20px;
                  background-color: #ffffff;
                  border: 1px solid #dddddd;
                  border-radius: 5px;
                  box-shadow: 0 0 5px rgba(0, 0, 0, 0.1);
                }
                
                .form-group {
                  margin-bottom: 20px;
                }
                
                .form-group label {
                  display: block;
                  font-weight: bold;
                  margin-bottom: 5px;
                }
                
                .form-group select,
                .form-group input {
                  width: 100%;
                  padding: 10px;
                  font-size: 14px;
                  border: 1px solid #dddddd;
                  border-radius: 3px;
                  box-sizing: border-box;
                }
                
                .form-group input[type="submit"] {
                  background-color: #005cbf;
                  color: #ffffff;
                  cursor: pointer;
                }
                
                .form-group input[type="submit"]:hover {
                  background-color: #004d99;
                }
                
                hr {
                  margin: 20px 0;
                  border: 0;
                  border-top: 1px solid #dddddd;
                }

                h5 {
                  color: #ff0000;
                  text-align: center; /* Center the text */
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Wi-Fi Manager</h1>
                <form method="post" action="configure">
                    <div class="form-group">
                        <label for="ssid">Select SSID:</label>
                        <select name="ssid" id="ssid" required>
                            <option value="" selected disabled>Select an SSID</option>
    """)
    while len(ssids):
        ssid = ssids.pop(0)
        client.sendall("""\
                            <option value="{0}">{0}</option>
        """.format(ssid))
    client.sendall("""\
                        </select>
                    </div>
                    <div class="form-group">
                        <label for="password">Password:</label>
                        <input type="password" name="password" id="password" required>
                    </div>
                    <div class="form-group">
                        <input type="submit" value="Connect">
                    </div>
                </form>
            </div>
            <hr />
            <h5>
                <span style="color: #005cbf;">
                    Your SSID and password information will be saved into the "%(filename)s" file in your ESP module for future usage.
                    Be careful about security!
                </span>
            </h5>
            <hr />
        </body>
        </html>
    """ % dict(filename=NETWORK_PROFILES))
    client.close()


def handle_configure(client, request):
    match = ure.search("ssid=([^&]*)&password=(.*)", request)

    if match is None:
        send_response(client, "Parameters not found", status_code=400)
        return False
    # version 1.9 compatibility
    try:
        ssid = match.group(1).decode("utf-8").replace("%3F", "?").replace("%21", "!")
        password = match.group(2).decode("utf-8").replace("%3F", "?").replace("%21", "!")
    except Exception:
        ssid = match.group(1).replace("%3F", "?").replace("%21", "!")
        password = match.group(2).replace("%3F", "?").replace("%21", "!")

    if len(ssid) == 0:
        send_response(client, "SSID must be provided", status_code=400)
        return False

    if do_connect(ssid, password):
        response = """\
            <html>
            <head>
                <title>Wi-Fi Manager</title>
                <style>
                    body {
                      background-color: #e9f5ff;
                      font-family: Arial, sans-serif;
                    }
                    
                    .success-message {
                      text-align: center;
                      margin: 40px 0;
                      color: #ff0000;
                    }
                </style>
            </head>
            <body>
            <!-- Success message -->
              <div class="success-message">
                <h1 style="color: #5e9ca0;">
                  <span style="color: #005cbf;">
                    ESP successfully connected to WiFi network %(ssid)s.
                  </span>
                </h1>
              </div>
            </body>
            </html>
        """ % dict(ssid=ssid)
        send_response(client, response)
        time.sleep(1)
        wlan_ap.active(False)
        try:
            profiles = read_profiles()
        except OSError:
            profiles = {}
        profiles[ssid] = password
        write_profiles(profiles)

        time.sleep(5)

        # Return the SSID and password to the caller (optional)
        return ssid, password
    else:
        response = """\
            <html>
                <center>
                    <h1 style="color: #5e9ca0; text-align: center;">
                        <span style="color: #ff0000;">
                            ESP could not connect to WiFi network %(ssid)s.
                        </span>
                    </h1>
                    <br><br>
                    <form>
                        <input type="button" value="Go back!" onclick="history.back()"></input>
                    </form>
                </center>
            </html>
        """ % dict(ssid=ssid)
        send_response(client, response)
        return False



def handle_not_found(client, url):
    send_response(client, "Path not found: {}".format(url), status_code=404)


def stop():
    global server_socket

    if server_socket:
        server_socket.close()
        server_socket = None


def start(port=80):
    global server_socket

    addr = socket.getaddrinfo('0.0.0.0', port)[0][-1]

    stop()

    wlan_sta.active(True)
    wlan_ap.active(True)

    wlan_ap.config(essid=ap_ssid, password=ap_password, authmode=ap_authmode)

    server_socket = socket.socket()
    server_socket.bind(addr)
    server_socket.listen(1)
    
    ## Upate popup here: 
    print('Connect to WiFi ssid ' + ap_ssid + ', default password: ' + ap_password)
    print('and access the ESP via your favorite web browser at 192.168.4.1.')
    print('Listening on:', addr)
    esphand.alertUser(alertType = " Warning!", message = "No WiFi", displayState = 1, status = 8) 

    while True:
        if wlan_sta.isconnected():
            wlan_ap.active(False)
            return True

        client, addr = server_socket.accept()
        print('client connected from', addr)
        try:
            client.settimeout(5.0)

            request = b""
            try:
                while "\r\n\r\n" not in request:
                    request += client.recv(512)
            except OSError:
                pass

            # Handle form data from Safari on macOS and iOS; it sends \r\n\r\nssid=<ssid>&password=<password>
            try:
                request += client.recv(1024)
                print("Received form data after \\r\\n\\r\\n(i.e. from Safari on macOS or iOS)")
            except OSError:
                pass
            
            # Skip invalid requests
            #print("Request is: {}".format(request))
            if "HTTP" not in request:  
                continue

            # version 1.9 compatibility
            try:
                url = ure.search("(?:GET|POST) /(.*?)(?:\\?.*?)? HTTP", request).group(1).decode("utf-8").rstrip("/")
            except Exception:
                url = ure.search("(?:GET|POST) /(.*?)(?:\\?.*?)? HTTP", request).group(1).rstrip("/")
            print("URL is {}".format(url))

            if url == "":
                handle_root(client)
            elif url == "configure":
                handle_configure(client, request)
            else:
                handle_not_found(client, url)

        finally:
            client.close()