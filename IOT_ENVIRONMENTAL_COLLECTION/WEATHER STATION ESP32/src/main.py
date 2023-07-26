#------------- Weather Station Circuit Code -------------------------#

import network
import esp
import espnow
import utime
import usocket as socket
import uasyncio as asyncio
from machine import Pin, UART
import ubluetooth as bluetooth
import wifimgr
import machine
import _thread as thread



class ESP32Handler():
    
    def __init__(self):
        
        # Instantiate ESP32 ESPNow credentials 
        self.id = 1
        self.senderMacAddress = " "
        self.peerList = [b'SENSOR-STATION-ESP-MAC-ADDRESS']
        
        # Initialise UART communication
        self.uartnum = 2
        self.uart = UART(self.uartnum, 9600)
        self.uart.init(9600, tx=25, rx=26)
        self.end_cmd= b'\xFF\xFF\xFF'
        
        # Instantiate ESP32 Bluetooth Credentials
        self.bluetooth_name = "J-WSTA"
        
        # Instantiate server side credentials
        self.port = 6000
        self.hostName = " "
        
        # Instantiate time stamps
        self.updateTime = "21:15:00"
        self.forecastTime = "00:15:00"
        
        # Instantiate weather data
        self.dailyDataDict = {"Date": "N/A", "MinTemp": "N/A", "MaxTemp": "N/A", "WindSpeed9am": "N/A", "WindSpeed3pm": "N/A", "Humidity9am": "N/A", "Humidity3pm": "N/A", "Pressure9am": "N/A", "Pressure3pm": "N/A", "Temp9am": "N/A", "Temp3pm": "N/A"}
        self.hourlyTemp = []
        
        # Instantiate zambretti list
        self.zambrettiList = []
        
        
    def sendWifiCredentials(self, network_password, network_ssid):
        
        # Set the Bluetooth name
        bluetooth_name = self.bluetooth_name
        ble = bluetooth.BLE()

        # Create a BLE service
        service_uuid = bluetooth.UUID("6E400001-B5A3-F393-E0A9-E50E24DCCA9E")

        # Register the service
        ble.gatts_register_services([(service_uuid, [])])

        # Characteristic for SSID
        ssid_characteristic_uuid = bluetooth.UUID("6E400002-B5A3-F393-E0A9-E50E24DCCA9E")

        # Characteristic for password
        password_characteristic_uuid = bluetooth.UUID("6E400003-B5A3-F393-E0A9-E50E24DCCA9E")

        # Register the characteristics and set their initial values
        ble.gatts_setattr(ssid_characteristic_uuid, network_ssid)
        ble.gatts_setattr(password_characteristic_uuid, network_password) 

        # Advertise the BLE service
        ble.gap_advertise(100, bytearray([bluetooth.ADV_TYPE_NAME_COMPLETE, len(bluetooth_name)]) + bytearray(bluetooth_name, 'utf-8'))

        # Scan for nearby BLE devices with the custom service
        receiver_address = None
        nearby_devices = ble.gap_scan(5)  # Scan for 5 seconds
        for device in nearby_devices:
            if device.rssi < -80 and service_uuid in device.services():
                receiver_address = device.addr
                break

        if receiver_address is not None:
            # Connect to the receiver
            connection_handle = ble.gap_connect(receiver_address)

            # Send encrypted Wi-Fi credentials to the receiver
            ble.gatts_notify(connection_handle, password_characteristic_uuid)
            ble.gatts_notify(connection_handle, ssid_characteristic_uuid)

            # Close the connection
            ble.gap_disconnect(connection_handle)
        else:
            print("Receiver not found.")
        
    async def getDateandTime(self):
            '''
            This method is responsible for getting the current date and time by using the localtime function, and returning these values as variables.
            returns:
                current_date: the current date
                current_time: the current time
            '''
            
            # Get current local time
            current = utime.localtime()

            # Format current date 
            current_date = "{:02d}/{:02d}/{}".format(current[2], current[1], current[0])

            # Format current time
            current_time = "{:02d}:{:02d}:{:02d}".format(current[3], current[4], current[5])
            
            await asyncio.sleep(0)
            
            return current_date, current_time
        
    async def addDataToCSV(self, dailyData):
            '''
            This method is responsible for taking the retrieved data (date, time, temperature, etc.) and appending it to the CSV file by establishing a connection with the
            python client and sending data, and then recieving the zambretti prediction as a response.
            params:
                dailyData: daily data acquired
            returns:
                responseDate: zambretti prediction number
            '''
            # Convert dictionary to list of values
            dailyData = list(dailyData.values())
            
            # Convert list to string
            dailyData = ' '.join([str(elem) for elem in dailyData])
            
            # Get instance
            server_socket = socket.socket() 
            
            # Get address info
            server_address = socket.getaddrinfo(self.hostName, self.port)[0][-1]
            
            # Bind the host address and port together 
            server_socket.bind(server_address)
            
            # Configure how many clients the server can listen to simultaneously
            server_socket.listen(1)
            
            # Set "time out" waiting time for server-client to establish connection (acts as countdown)
            server_socket.settimeout(120)
            
            try:
                
                # Establish new connection
                conn, address = server_socket.accept()
                
                # Disable countdown once connection is established
                server_socket.settimeout(None)
                
            except:

                # Assign response data string
                responseData = "5,5"
                
                return responseData
            
            #print("Connection from: " + str(address) + " established")
            
            # Send data to the client
            conn.send(dailyData.encode())
            
            # Assign response data to variable
            responseData = conn.recv(1024).decode()

            # Close the connection
            conn.close()
            
            return responseData
        
    async def convertBStringToList(self, msg):
            '''
            This method is responsible for taking byte string as an argument and converting it to a list which is returned
            params:
                msg: byte string message recieved from ESPNow peer
            returns:
                msgList: string of message deconstructed into a list
            '''
            msgString = msg.decode('utf-8')
            
            msgList = list(msgString.split(" "))
            
            await asyncio.sleep(0)
            
            return msgList
        
    async def checkMessage(self, msgList):
        
            msgType = msgList[0]
            
            if msgType == "hourlyUpdate":
                
                temp = msgList[2]
                
                # Append variable value to hourly list
                self.hourlyTemp.append(temp)
                
                # Update Nextion Temperature, Pressure and Humidity Labels
                await self.nextionBME280(temp, press, hum)
                
            elif msgType == "keyUpdate":
                
                temp, press, hum, windspeed, moisture = msgList[2], msgList[3], msgList[4], msgList[5], msgList[6]
                
                # Append variable values to hourly list 
                self.hourlyTemp.append(temp)
                
                timeStamp = msgList[7]
                timeStampHour = timeStamp[0:2]
                
                if timeStampHour == "09":
                    
                    # Update daily data dictionary
                    self.dailyDataDict.update(Temp9am = temp)
                    self.dailyDataDict.update(Pressure9am = press)
                    self.dailyDataDict.update(Humidity9am = hum)
                    self.dailyDataDict.update(WindSpeed9am = windspeed)
                    
                else:
                    
                    # Update daily data dictionary
                    self.dailyDataDict.update(Temp3pm = temp)
                    self.dailyDataDict.update(Pressure3pm = press)
                    self.dailyDataDict.update(Humidity3pm = hum)
                    self.dailyDataDict.update(WindSpeed3pm = windspeed)
                    
                # Update Nextion HMI Labels
                await self.nextionUpdate(temp, press, hum, windspeed, moisture)
                
            else:
                pass
    
            
    async def nextionUpdate(self, temp, press, hum, windspeed, moisture):
            '''
            This method is responsible for taking the Sensor readings as arguments and writing them to
            the nextion display
            params:
                temp: temperature reading recieved from BME280 
                press: pressure reading recieved from BME280 
                hum: humidity reading recieved from BME280 
                windspeed: windspeed reading recieved from Anemometer
                moisture: moisture reading recieved from soil moisture station
            '''
            cmd = "temperature.txt=\""+temp+"\""
            self.uart.write(cmd)
            self.uart.write(self.end_cmd)
            utime.sleep_ms(100)
            self.uart.read()
            
            cmd = "pressure.txt=\""+press+"\""
            self.uart.write(cmd)
            self.uart.write(self.end_cmd)
            utime.sleep_ms(100)
            self.uart.read()
            
            cmd = "humidity.txt=\""+hum+"\""
            self.uart.write(cmd)
            self.uart.write(self.end_cmd)
            utime.sleep_ms(100)
            self.uart.read()
            
            cmd = "windspeed.txt=\""+windspeed+"\""
            self.uart.write(cmd)
            self.uart.write(self.end_cmd)
            utime.sleep_ms(100)
            self.uart.read()
            
            cmd = "moisture.txt=\""+str(moisture)+"\""
            self.uart.write(cmd)
            self.uart.write(self.end_cmd)
            utime.sleep_ms(100)
            self.uart.read()
            
            await asyncio.sleep(0)
            
    async def updateForecast(self, forecasts):
            '''
            This method is responsible for taking the zambretti predictions as arguments and writing them to
            the nextion display
            params:
                forecasts: zambretti prediction list
            '''
            cmd= "earlyforecast.pic={}".format(zambretti[0])
            self.uart.write(cmd)
            self.uart.write(self.end_cmd)
            utime.sleep_ms(100)
            self.uart.read()
            
            cmd= "lateforecast.pic={}".format(zambretti[1])
            self.uart.write(cmd)
            self.uart.write(self.end_cmd)
            utime.sleep_ms(100)
            self.uart.read()
            
            await asyncio.sleep(0)
            
    def alertUser(self, alertType, message, displayState, status):
        '''This method is responsible for displaying an alert box on the nextion HMI when the WiFi is connected or disconnected
        '''
        
        refreshState = 0
        
        # Hide Alert Box Content -----------------------
        
        cmd = "vis warnbox,{}".format(refreshState)
        self.uart.write(cmd)
        self.uart.write(self.end_cmd)
        
        cmd = "vis warnheader,{}".format(refreshState)
        self.uart.write(cmd)
        self.uart.write(self.end_cmd)
        
        cmd = "vis message,{}".format(refreshState)
        self.uart.write(cmd)
        self.uart.write(self.end_cmd)
        
        cmd = "vis status,{}".format(refreshState)
        self.uart.write(cmd)
        self.uart.write(self.end_cmd)
        
        # -----------------------------------------------
        
        utime.sleep(2)
        
        cmd = "vis warnbox,{}".format(displayState)
        self.uart.write(cmd)
        self.uart.write(self.end_cmd)

        cmd = "warnheader.txt=\""+alertType+"\""
        self.uart.write(cmd)
        self.uart.write(self.end_cmd)

        cmd = "vis warnheader,{}".format(displayState)
        self.uart.write(cmd)
        self.uart.write(self.end_cmd)

        cmd = "message.txt=\""+message+"\""
        self.uart.write(cmd)
        self.uart.write(self.end_cmd)

        cmd = "vis message,{}".format(displayState)
        self.uart.write(cmd)
        self.uart.write(self.end_cmd)

        cmd= "status.pic={}".format(status)
        self.uart.write(cmd)
        self.uart.write(self.end_cmd)

        cmd = "vis status,{}".format(displayState)
        self.uart.write(cmd)
        self.uart.write(self.end_cmd)
            

async def main():
    
    root = ESP32Handler()
    
    # Initialise the ESPNow module
    e = espnow.ESPNow()
    e.active(True)
    
    # Add peers for ESPNow communication
    for peer in root.peerList:
        e.add_peer(peer)
        
    # Initialize the Wi-Fi manager and connect to Wi-Fi 
    wlan = wifimgr.get_connection()
    
    if wlan is None:
        
        # Show popup here!!!
        root.alertUser(alertType = " Warning!", message = "No WiFi", displayState = 1, status = 8) 
        
        while True:
            pass # Stop from moving forward
    
    try:
        
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('', 80))
        s.listen(5)
        
    except OSError as e:
        # Reset system with network credentials to forget the socket
        machine.reset()
      
    
    network_ssid = wifimgr.connected_ssid
    network_password = wifimgr.connected_password

    print(network_password, network_ssid)
    
    if network_ssid is not None and network_password is not None:
        root.sendWifiCredentials(network_password, network_ssid)

    # Declare WLAN station as variable
    station = network.WLAN(network.STA_IF)

    # If statement checking if the ESP is connected to WiFi 
    if station.isconnected() == True:

        # Update sender's MAC address variable 
        root.senderMacAddress = station.config('mac')
        
        # Update host name variable
        root.hostName = station.ifconfig()[2]
        
        #esp.on_receive(on_receive)

    #print(root.senderMacAddress)
         
    while True:
        
        # Run function to get current date and time
        asyncio.create_task(root.getDateandTime())
        current_date, current_time = await root.getDateandTime()
         
        # Update daily data dictionary
        root.dailyDataDict.update(Date = current_date)
         
        while current_time == root.updateTime:
            
            # Convert hourly temperature list values to float
            tempValues = [float(i) for i in root.hourlyTemp]
            
            # Find min and max of temperature, humidity, and pressure
            minTemp = min(tempValues)
            maxTemp = max(tempValues)
            
            # Update Dictionary Min and Max Temperature values
            root.dailyDataDict.update(MinTemp = str(minTemp))
            root.dailyDataDict.update(MaxTemp = str(maxTemp))
     
            # Run function to update CSV file (data set)
            asyncio.create_task(root.addDataToCSV(root.dailyDataDict))
            zambrettiPredictions = await root.addDataToCSV(root.dailyDataDict)

            # Append zambretti predictions to zambretti list
            root.zambrettiList = zambrettiPredictions.split(",")
            root.zambrettiList = [int(i) for i in zambrettiList]
            
            # Empty lists and restore dictionary values to default values
            root.dailyDataDict = {"Date": "N/A", "MinTemp": "N/A", "MaxTemp": "N/A", "WindSpeed9am": "N/A", "WindSpeed3pm": "N/A", "Humidity9am": "N/A", "Humidity3pm": "N/A", "Pressure9am": "N/A",
                      "Pressure3pm": "N/A", "Temp9am": "N/A", "Temp3pm": "N/A"}
            root.hourlyTemp = []
            
            utime.sleep(1)

            # Exit while loop to continue as normal
            break
         
        while current_time == root.forecastTime:
         
            asyncio.create_task(root.updateForecast(root.zambrettiList))
            await root.updateForecast(root.zambrettiList)
             
            # Empty zambretti list 
            root.zambrettiList = []
            
            utime.sleep(1)
            
            # Exit while loop to continue as normal
            break
        
        
        host, msg  = e.recv()
        
        # If statement to query message
        if msg is not None and host is not None:

            # Run function to convert message byte-string into list and asign result to variable
            asyncio.create_task(root.convertBStringToList(msg))
            msgList = await root.convertBStringToList(msg)
            
            asyncio.create_task(root.checkMessage(msgList))
            await root.checkMessage(msgList)
            
            utime.sleep(1)
            
         
        #print(current_time)
        utime.sleep(1)
            
if __name__ == "__main__":
    
    utime.sleep(3)
    asyncio.run(main())