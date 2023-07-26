import warnings
warnings.filterwarnings("ignore")
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.neighbors import KNeighborsRegressor
from sklearn.tree import DecisionTreeRegressor
from sklearn.metrics import mean_squared_error
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import socket
import csv

class MachineLearning():

    def __init__(self):
        self.host =  'MY-ESP32-IP-ADDRESS'
        self.port = 6000  # Socket server port number
        self.client_socket = socket.socket()  # Instantiate client socket
        self.csvFile = "weatherData.csv"
        self.altitude = 590

    def client_program(self):

        client_socket = self.client_socket
        client_socket.connect((self.host, self.port))  # Connect to server

        # Receive response
        data = client_socket.recv(1024).decode()

        # Convert data string to list 
        data = list(data.split(" "))

        # Convert list elements to floats if possible
        newData = []

        for ele in data:
            try:
                newData.append(float(ele))
            except:
                newData.append(ele)
        
        # Call function to update CSV file with the new data collected
        self.updateCSV(newData)

        # Call function run machine-learning function and return prediction
        predictions = self.predictWeatherParams()

        # Convert prediction list values to floats
        predictions = [float(i) for i in predictions]

        # Get seaLevelPressure for 9am predictions
        seaLevelPressure9am = self.getStationSeaLevel(predictions[6], self.altitude, predictions[8])
        #print(seaLevelPressure9am)

        # Get seaLevelPressure for 3pm predictions
        seaLevelPressure3pm = self.getStationSeaLevel(predictions[7], self.altitude, predictions[9])
        #print(seaLevelPressure3pm)

        # Calculate 9am zambretti value by parsing 9am pressure prediction and atmospheric pressure value at sea level for 9am  
        zambretti9am = self.calculateZambretti(predictions[6], float(seaLevelPressure9am))
        #print(zambretti9am)

        # Calculate 3pm zambretti value by parsing 3pm pressure prediction and atmospheric pressure value at sea level for 9am  
        zambretti3pm = self.calculateZambretti(predictions[7], float(seaLevelPressure3pm))
        #print(zambretti3pm)

        # Format zambretti values
        zambrettiForecasts = f"{zambretti9am},{zambretti3pm}"

        # Send zambretti prediction back to Weather Station ESP32
        client_socket.send(zambrettiForecasts.encode())

        # Close connetion 
        client_socket.close()

    def getNumOfEntries(self):
        '''
        This method is responsible for checking how many rows are in the weather data file and returning the value.
        returns:
            numOfEntries: the number of rows present in the CSV file.
        '''

        # Opening the CSV file
        with open(self.csvFile, mode="r") as file:

            # Reading the CSV file
            csvFile = csv.reader(file)

            # Getting the header of the file
            header = next(csvFile)

            # Checking if the file is empty
            if header != None:

                # Get number of data entries using the sum method and a for loop
                numOfEntries = sum(1 for row in csvFile)

            else:

                # Add header to CSV file
                df = pd.read_csv(self.csvFile, header=None, names=["Date", "MinTemp", "MaxTemp", "Windspeed9am", "Windspeed3pm", "Humidity9am", "Humidity3pm", "Pressure9am", "Pressure3pm", "Temp9am", "Temp3pm"])
                
                # Get number of entries using the sum method and a for loop
                numOfEntries = sum(1 for row in csvFile)
            
            return numOfEntries
        
    def updateCSV(self, newData):
        '''
        This method is responsible for taking the newly acquired data and appending it to the existing dataset (CSV file)
        params:
            newData: newly acquired data
        '''

        # --- Read csv file --- #
        df = pd.read_csv(self.csvFile)

        entries = self.getNumOfEntries()

        # Create row data out of new data list elements
        row = {
            "Date" : [newData[0]],
            "MinTemp" : [newData[1]],
            "MaxTemp" : [newData[2]],
            "WindSpeed9am" : [newData[3]],
            "WindSpeed3pm" : [newData[4]], 
            "Humidity9am" : [newData[5]],
            "Humidity3pm" : [newData[6]],
            "Pressure9am" : [newData[7]],
            "Pressure3pm" : [newData[8]],
            "Temp9am" : [newData[9]],
            "Temp3pm" : [newData[10]]
        }

        if entries >= 20538:

            # Remove First entry from dataset 
            df = df.drop(df.index[0])

            # writing into the file
            df.to_csv(self.csvFile, index=False)

        # Create data frame using row data
        df = pd.DataFrame(row)

        # Append new data frame to CSV file
        df.to_csv(self.csvFile, mode='a', index=False, header=False)

    def predictWeatherParams(self):
        '''This method is responsible for loading the historical data and using a list of machine learning models to predict tomorrows forecast'''

        # Load the dataset
        data = pd.read_csv('weatherData.csv')

        # --- Remove "N/A" values --- #
        data = pd.read_csv(self.csvFile, na_values=["not available", "n/a", "N/A"])

        # Remove rows with at least one Nan value (Null value)
        data = data.dropna()

        # Sort the dataset by date in ascending order
        data = data.sort_values('Date')

        # Select the last row of the DataFrame
        last_row = data.iloc[-1]

        # Convert last row to list (2D array)
        row = last_row.values.tolist()

        # Convert last row list into 1D list
        recentEntry = row
        #print(recentEntry)

        # Select the last 10 days' data entries
        last_10_days_data = data.tail(10)

        # Extract the relevant columns for the prediction comparison graph
        real_values = last_10_days_data['Pressure3pm']
        real_values= real_values.values.tolist()

        # Calculate rolling average across the last 30 data entries
        window_size = 30
        rolling_average_data = data.rolling(window_size).mean().dropna()

        # Define the input features and target variables
        features = ['MinTemp', 'MaxTemp', 'WindSpeed9am', 'WindSpeed3pm', 'Humidity9am', 'Humidity3pm', 'Pressure9am', 'Pressure3pm', 'Temp9am', 'Temp3pm']
        targets = ['MinTemp', 'MaxTemp', 'WindSpeed9am', 'WindSpeed3pm', 'Humidity9am', 'Humidity3pm', 'Pressure9am', 'Pressure3pm', 'Temp9am', 'Temp3pm']

        # Prepare input features for the last 10 days
        X_last_10_days = last_10_days_data[features]

        X = rolling_average_data[features]
        y = rolling_average_data[targets]

        # Split the dataset into training and testing sets
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        # Define the models to compare
        models = [
            LinearRegression(),
            RandomForestRegressor(),
            KNeighborsRegressor(),
            DecisionTreeRegressor()
        ]

        # Train and evaluate each model
        model_mses = []
        for model in models:
            model.fit(X_train, y_train)
            joblib.dump(model, 'weather_predictor.sav')
            y_pred = model.predict(X_test)
            mse = mean_squared_error(y_test, y_pred)
            model_mses.append(mse)

        # Find the model with the smallest MSE
        best_model_index = model_mses.index(min(model_mses))
        best_model = models[best_model_index]

        print("Best Model MSE:", min(model_mses))
        print("Best Model:", best_model)

        # Make predictions for the last 10 days using the best model
        predictions = best_model.predict(X_last_10_days)
        predicted_values = predictions

        # Extract the values for the 'Pressure3pm' column from the predicted values
        predicted_pressure_3pm = predicted_values[:, features.index('Pressure3pm')]
        predicted_pressure_3pm =  [ '%.1f' % elem for elem in predicted_pressure_3pm]
        predicted_pressure_3pm = [float(i) for i in predicted_pressure_3pm]

        print("Last 10 Day's Pressure at 3pm Real values:",real_values)
        print("Last 10 Day's Pressure at 3pm Predictions:", predicted_pressure_3pm)

        # Plotting the comparison graph
        #plt.figure(figsize=(10, 6))
        #plt.plot(range(10), real_values, marker='o', color='red', label='Real Values (Pressure3pm)')
        #plt.plot(range(10), predicted_pressure_3pm, marker='o', color='blue', label='Predicted Values')

        #plt.title('Real Values vs Predicted Values')
        #plt.xlabel('Entry')
        #plt.ylabel('Pressure3pm')
        #plt.legend()
        #plt.show()

        # Prepare input features for the next day (assuming you have data for the next day)
        last_30_days_data = data.tail(window_size)  # Select the last 30 days' data entries
        next_day_rolling_average = last_30_days_data.mean()  # Calculate the rolling average
        next_day_features = next_day_rolling_average[features].values.reshape(1, -1)  # Reshape the features to match the model's expectations

        # Make predictions for the next day's weather parameters using the best model
        next_day_predictions = best_model.predict(next_day_features)
        next_day_predictions = pd.DataFrame(next_day_predictions, columns=targets)

        print("\nNext Day's Weather Predictions:")#, predictions
        print(next_day_predictions.to_string(index=False))

        predictionList = list(next_day_predictions.values[0])

        # Round list elements to 2 decimal places
        formattedPredictions = [ '%.2f' % elem for elem in predictionList]

        return formattedPredictions

    def getStationSeaLevel(self, p, h, t):
        '''
        This method is responsible for taking the pressure (p), altitude (h), and temperature (t) as arguments and using a mathematical equation
        to compute the atmospheric pressure reduced to sea level, and returning this value.
        params:
            p: timestamps (9am or 3pm) barometric pressure prediction
            h: altitude for the UK
            t: timestamps (9am or 3pm) temperature prediction
        returns:
            seaLevelPressure: atmospheric pressure reduced to sea level
        '''

        seaLevelPressure = p * pow(1-0.0065*h/(t+0.0065*h+273.15),-5.275)

        seaLevelPressure = format(seaLevelPressure, '.2f')

        return seaLevelPressure
    
    def calculateZambretti(self, predictedPressure, atmosPressure):

        trend = ""

        # If the pressure condition is rising 
        if atmosPressure > predictedPressure:

            zambretti = 179 - ((2*atmosPressure)/129)
            trend = "rising"
        # If the pressure condition is falling
        elif atmosPressure < predictedPressure:

            zambretti = 130 - (atmosPressure / 81)
            trend = "falling"
        # If the pressure condition is steady
        else:
            
            zambretti = 147- (5 * atmosPressure / 376)
            trend = "steady"

        zambretti = round(zambretti)

        if(zambretti>32):

            zambretti = round(zambretti % 32)

        if trend == "falling":
            if zambretti in range(3):
                zambrettiKey = 2
            elif zambretti in range(3, 6):
                zambrettiKey = 3
            elif zambretti in range(6, 10):
                zambrettiKey = 6
        elif trend == "steady":
            if zambretti in range(3):
                zambrettiKey = 2
            elif zambretti in range(3, 7):
                zambrettiKey = 3
            elif zambretti in range(7, 10):
                zambrettiKey = 6
            elif zambretti == 10:
                zambrettiKey = 6
        elif trend == "rising":
            if zambretti in range(5):
                zambrettiKey = 2
            elif zambretti in range(5, 12):
                zambrettiKey = 3
            elif zambretti in range(12, 14):
                zambrettiKey = 4

        return zambrettiKey
    
if __name__ == '__main__':
    root = MachineLearning()
    root.client_program()