#------------- Sensor Station Circuit Code -------------------------#

import uasyncio as asyncio
import BME280
import esp
import espnow
import network
import utime
import urequests
from network import WLAN
from machine import Pin, ADC, SoftI2C as I2C
import ucryptolib
import ubluetooth as bluetooth


class ESP32Handler():
    
    def __init__(self):
        
        # Instantiate BME280 dependables
        self.i2c = I2C(scl=Pin(22), sda=Pin(21), freq=10000)
        self.bme = BME280.BME280(i2c=self.i2c)
        
        # Instantiate anemometer technical variables
        self.minVoltage = 0.4 # Defines the minimum output voltage from the anemometer
        self.maxVoltage = 2.0 # Defining the maximum output voltage from the anemometer
        self.minWindSpeed = 0.0 # Windspeed (m/s) in correspondance to minimum voltage
        self.maxWindSpeed = 32.4 # Windspeed (m/s) in correspondance to maximum voltage

        # Instantiate soil moisture conditional parameters
        self.airValue = 2828 #3014 #2700
        self.waterValue = 1011 #1028 #992
        
        # Instantiate ESP32 ESPNow credentials 
        self.id = 2
        self.senderMacAddress = " "
        self.peerList = [b'WEATHER-STATION-ESP-MAC-ADDRESS']
        
        # Instantiate variables for handling Thingspeaks
        self.http_header = {'Content-Type': 'application/json'}
        self.thingspeakAPIKey = 'MY-API-KEY'
        
        # Instantiate time-stamp lists
        self.hourTimeStamps = []
        self.keyTimeStamps = ['09:00:00', '15:00:00']
        
        # Instantiate ESP32 Bluetooth Credentials
        self.bluetooth_name = "J-SSTA"
        self.receiver_key = b'\xd9\x02.0\xce\x8a\x1b\x1d\x11\xf7j\x00\x113\xb05\xa4q\xf1cp.\x88t\x81A\xcci\xbb\t\xd0\x0c'
        self.ble = bluetooth.BLE()
    
        # Create a BLE service
        self.service_uuid = bluetooth.UUID("6E400001-B5A3-F393-E0A9-E50E24DCCA9E")
        self.ble.gatts_register_services([(self.service_uuid, [])])

        # Characteristic for SSID
        self.ssid_characteristic_uuid = bluetooth.UUID("6E400002-B5A3-F393-E0A9-E50E24DCCA9E")

        # Characteristic for password
        self.password_characteristic_uuid = bluetooth.UUID("6E400003-B5A3-F393-E0A9-E50E24DCCA9E")
        
        # For loop for inputting hourly time stamps
        for time in range(0,24):
            if time in range(0,10):
                self.hourTimeStamps.append("0{}:00:00".format(time))
            else:
                self.hourTimeStamps.append("{}:00:00".format(time))
            
  
    def getConnection(self, station, ssid, password):
        '''
        This method is responsible for establishing a connection with the WiFi router based on its SSID and password.
        After which the mac address is updated.
        '''
        station.active(True)
        station.connect(ssid, password)
        self.senderMacAddress = station.config('mac')
        
    async def getDateandTime(self):
            '''
            This method is responsible for getting the current date and time by using the localtime function, and returning these values as variables.
            returns:
                current_date: the current date
                current_time: the current time
            '''
            # Get current local time
            current = utime.localtime()
            
            # Format current time
            current_time = "{:02d}:{:02d}:{:02d}".format(current[3], current[4], current[5])
            
            await asyncio.sleep(0)
            
            return current_time
    
    async def checkTime(self, current_time):
            '''
            This method is responsible for taking the current time as an argument and querying its value
            to determine the message type that is to be sent to the weather station. This value is then returned
            params:
                current_time: the current time
            returns:
                messageType: the message type
            '''
            
            # If statement to query if current date and time is amongst the declared hour time stamps or is equivalent to the update time
            if current_time in self.hourTimeStamps and current_time not in self.keyTimeStamps:
                messageType = "hourlyUpdate"
            elif current_time in self.hourTimeStamps and current_time in self.keyTimeStamps:
                messageType = "keyUpdate"
            else:
                messageType = "normalUpdate"
            
            await asyncio.sleep(0)
                
            return messageType
        
    def map_range(self, x, in_min, in_max, out_min, out_max):
        """
        Maps a number from one range to another.
        Note: This implementation handles values < in_min differently than arduino's map function does.

        :return: Returns value mapped to new range
        :rtype: float
        """
        in_range = in_max - in_min
        in_delta = x - in_min
        if in_range != 0:
            mapped = in_delta / in_range
        elif in_delta != 0:
            mapped = in_delta
        else:
            mapped = 0.5
        mapped *= out_max - out_min
        mapped += out_min
        if out_min <= out_max:
            return max(min(mapped, out_max), out_min)
        return min(max(mapped, out_max), out_min)
        
    
    async def getSensorReadings(self):
            '''
            This method is responsible for returning the current sensor reading values from the sensors for the parameters temperature, pressure, humidty, and moisture.
            returns:
                temp: BME280 sensor temperature reading
                pres: BME280 sensor pressure reading
                hum: BME280 sensor humidity reading
                moisture: Capacitive soil moisture sensor reading
            '''
            
            # Handling of BME280 Sensor ------------------------------------
            
            bme = self.bme
            
            temp = bme.temperature
            pres = bme.pressure
            hum = bme.humidity
            
            # Remove unit digits from each string
            temp = temp[:-1]
            pres = pres[:-3]
            hum = hum[:-1]
            
            #---------------------------------------------------------------
            
            # Handling of Adafruit Anemometer ------------------------------
            
            # Declaring an ADC object 
            anemometerAnalogInput = ADC(Pin(35))
            
            # Setting the attenuation ratio to full range
            anemometerAnalogInput.atten(ADC.ATTN_11DB)
            
            # Reading the analog input value
            anemometerValue = float(anemometerAnalogInput.read())
            
            # Calculating the voltage
            voltage = (anemometerValue / 4095) * 3.3
            
            # If statement to convert voltage to wind speed using the range of max and min voltages and wind speed for the anemometer
            if voltage <= self.minVoltage:
                windspeed = 0.0
            else:
                # Calculating the windspeed by using map_range function
                windspeed = self.map_range(voltage, self.minVoltage, self.maxVoltage, self.minWindSpeed, self.maxWindSpeed)
                
            # Round the result
            windspeed = repr(round(windspeed, 1))
            
            windspeed = float(windspeed)
            
            #---------------------------------------------------------------
            
            # Handling of Capacitive Soil Moisture Sensor ------------------
            
            # Declaring an ADC object
            analogInput = ADC(Pin(34))
            
            # Setting the attenuation ratio to full range
            analogInput.atten(ADC.ATTN_11DB)
            
            # Reading the analog input value
            soilMoistureValue = analogInput.read()
            
            # Calculating the soil moisture percentage by using map_range function
            soilMoisturePercent = self.map_range(soilMoistureValue, self.airValue, self.waterValue, 0, 100)
            
            # Rounding the result
            moisture = repr(round(soilMoisturePercent, 1))
            
            #---------------------------------------------------------------
            
            await asyncio.sleep(0)
        
            return temp, pres, hum, windspeed, moisture
            
    
    async def configureDataPacket(self, messageType, temperature, pressure, humidity, windspeed, moisture, current_time):
            '''
            This method is responsible for recieving the sensor readings (temperature, pressure, humidity, and moisture) as arguments along with its ID
            and configuring these values into a data packet in string format that is returned.
            params:
                temperature: sensor reading for most recent temperature
                pressure: sensor reading for most recent pressure
                humidity: sensor reading for most recent humidity
                windspeed: sensor reading for most recent windspeed
                moisture: sensor reading for most recent soil moisture
            returns:
                dataPacket: configured data packet (string)
            '''
            espID = self.id
            
            dataList = [messageType, espID, temperature, pressure, humidity, windspeed, moisture, current_time]
            
            # Using list comprehension to convert data packet list to string
            dataPacket = ' '.join([str(elem) for elem in dataList])
            
            await asyncio.sleep(0)
            
            return dataPacket
        
    
    def updateThingspeaks(self, temperature, pressure, humidity, windspeed, moisture):
        '''
        This method is responsible for taking the sensor readings as an argument and organising a json topic to be then trying to publish (posting)
        it via the urequests module to the Thingspeak API. The status of the request is subsequently return as either success or failure.
        params:
            temperature: most recent temperature readings
            pressure: most recent pressure readings
            humidity: most recent humidity readings
            windspeed: most recent windspeed readings
            moisture: most recent soil moisture readings
        returns:
            status: status of request (success or failure)
        '''
        
        # Organise json
        sensor_readings = {'field1':temperature, 'field2':pressure, 'field3':humidity,'field4':windspeed, 'field5':moisture}
        
        # Try to send readings to Thingspeaks API - only works if WiFi still connected
        try:
            # Post readings (topic) to thingspeak API 
            request = urequests.post( 'http://api.thingspeak.com/update?api_key=' + self.thingspeakAPIKey, json = sensor_readings, headers = self.http_header )
            request.close()
            status = "Thingspeaks request (topic) sucessfuly published"
            
        except Exception as e:
            status = e
        
        return status
    
    async def sendESPMessage(self, dataPacket, e):
            '''
            This method is responsible for taking the data packet and instance of the espnow module and sending the data packet in a message via the espnow
            communication protocol. The status of the message is subsequently returned as either success or failure.
            params:
                dataPacket: configured data packet containing recent sensor readings (string)
            returns:
                status: status of espnow message (success or failure)
            '''
             
            utime.sleep(8)

            try:
                # Send data to ESPNow Peer 
                e.send(None,dataPacket,False)
                status = "ESPNow message sucessfuly sent"
                
            except:
                status = "FAIL"

            await asyncio.sleep(3)

            return status
        
        
    def xor_encrypt_decrypt(self, data, key):
        '''This method is responsible for decrypting data'''
        return bytes([a ^ b for a, b in zip(data, key)])
    
    def on_write_callback_handler(self, sender, value):
        
        if sender == self.password_characteristic_uuid:
            # Receive encrypted Wi-Fi credentials from the sender
            received_ssid = self.ble.gatts_getattr(self.ssid_characteristic_uuid)
            received_password = value

            # Decrypt the Wi-Fi credentials for the receiver
            ssid = self.xor_encrypt_decrypt(received_ssid, self.receiver_key).decode()
            password = self.xor_encrypt_decrypt(received_password, self.receiver_key).decode()

            # Declare WLAN station as variable
            station = network.WLAN(network.STA_IF)

            self.getConnection(station, ssid, password)
                

async def main():
    
    root = ESP32Handler()
    
    # Initialise the ESPNow module
    e = espnow.ESPNow()
    e.active(True)
    
    # Add peers for ESPNow communication
    for peer in root.peerList:
        e.add_peer(peer)
    
    # Register the callback function for handling incoming data
    root.ble.gatts_setattr(root.password_characteristic_uuid, root.on_write_callback_handler)

    # Advertise the BLE service
    root.ble.gap_advertise(100, bytearray([bluetooth.ADV_TYPE_NAME_COMPLETE, len(root.bluetooth_name)]) + bytearray(root.bluetooth_name, 'utf-8'))
    
    # Declare WLAN station as variable
    station = network.WLAN(network.STA_IF)
    
    # If statement checking if the ESP is connected to WiFi 
    if station.isconnected() == True:
        
        #print(" Connected!" + "\n")
        # Update sender's MAC address variable 
        root.senderMacAddress = station.config('mac')
    
    
    while True:
        
        # Run function to get current date and time
        asyncio.create_task(root.getDateandTime())
        current_time = await root.getDateandTime()
        
        while current_time in root.hourTimeStamps:
            
            # Determine message type based on current time
            asyncio.create_task(root.checkTime(current_time))
            messageType = await root.checkTime(current_time)
            
            # Get the sensor data for temperature, pressure, humidity, windspeed, and soil moisture
            asyncio.create_task(root.getSensorReadings())
            temperature, pressure, humidity, windspeed, moisture = await root.getSensorReadings()
            
            # Configure data packet
            asyncio.create_task(root.configureDataPacket(messageType, temperature, pressure, humidity, windspeed, moisture, current_time))
            dataPacket = await root.configureDataPacket(messageType, temperature, pressure, humidity, windspeed, moisture, current_time)
            
            print(dataPacket)
            
            # Delay before publishing topic
            utime.sleep(2)
            
            # Publish Sensor readings to Thingspeaks API via urequests
            requestStatus = root.updateThingspeaks(temperature, pressure, humidity, windspeed, moisture)
            
            # Send data packet via ESPNow
            asyncio.create_task(root.sendESPMessage(dataPacket, e))
            espStatus = await root.sendESPMessage(dataPacket, e)
            
            #print(espStatus, requestStatus)
            
            # Exit while loop to continue as normal
            break
       
        utime.sleep(1)
            
if __name__ == "__main__":
    
    utime.sleep(3)
    asyncio.run(main())
