from abc import ABC
import math
from pathlib import Path

import numpy as np
from beacon import create_beacons
from map import Map

from measurement import process_training_data
import file_helper as fh
import general_helper as gh
import constants as const


class BaseModel(ABC):


    def predict_position(self, rssi_measurement):
        pass


class GaussianProcessModel(BaseModel):

    def __init__(self, training_data_filepath: Path, prior,starting_point = [-3,-3],ending_point = [10,17],cell_size=1):
        self.beacon_positions, training_data = fh.load_training_data(training_data_filepath, windows=True)
        training_data = process_training_data(training_data,type=const.MeasurementProcess.MEDIAN)
        self.beacons = create_beacons(self.beacon_positions, training_data)
        self.area_map = Map(starting_point, ending_point, cell_size)
        self.prior = prior

    def predict_position(self, rssi_measurement,previous_cell = None):
        """
        for beacon in self.beacon_positions.keys():
            if beacon not in rssi_measurement.keys():
                rssi_measurement[beacon] = -100"""

        calculated_cells = self.area_map.calculate_cell_probabilities(rssi_measurement,self.beacons,previous_cell,self.prior)

        sorted_cells = sorted(calculated_cells, key=lambda c: c.probability, reverse=False)


        return sorted_cells[0].center


class GaussianKNNModel(GaussianProcessModel):



    def predict_position(self, rssi_measurement,previous_cell = None):

        """
        for beacon in self.beacon_positions.keys():
            if beacon not in rssi_measurement.keys():
                rssi_measurement[beacon] = -100"""

        calculated_cells = self.area_map.calculate_cell_probabilities(rssi_measurement,self.beacons,previous_cell,self.prior)

        sorted_cells = sorted(calculated_cells, key=lambda c: c.probability, reverse=False)

        k = 3
        first_k = sorted_cells[:k]

        position = np.zeros(2)

        prob_sum = sum([abs(cell.probability) for cell in first_k])
        for cell in first_k:
            position += (abs(cell.probability) / prob_sum) * cell.center


        return position


class WKNN(BaseModel):

    def __init__(self, training_data_filepath:Path):
        self.beacon_positions, training_data = fh.load_training_data(training_data_filepath, windows=True)
        self.training_data = process_training_data(training_data,type = const.MeasurementProcess.MEDIAN)


    def predict_position(self,rssi_measurement, k=3):
        """
        for beacon in self.beacon_positions.keys():
            if beacon not in rssi_measurement.keys():
                rssi_measurement[beacon] = -100"""


        distances = {} 
        for beacon, data in self.training_data.items():
            
            for line in data:
                d_hash = gh.hash_2D_coordinate(*line[1:])
                if not d_hash in distances.keys():
                    distances[d_hash] = [np.array(line[1:]),0,1*10**-6]
                if beacon in rssi_measurement.keys():
                    distances[d_hash][1] +=  (np.square(line[0] - rssi_measurement[beacon]))**2
                    distances[d_hash][2] += 1


        for h, data in distances.items():
            distances[h][1] = np.sqrt(data[1]/distances[h][2])


        sorted_points = sorted(list(distances.values()), key = lambda p : p[1])
        first_k = sorted_points[:k]

        position = np.zeros(2)

        distance_sum = sum([distance for _, distance, _ in first_k])
        for point, distance, _ in first_k:
            position += (distance / (distance_sum+1*10**-6)) * point

        return position

class KNN(BaseModel):

    def __init__(self, training_data_filepath:Path):
        self.beacon_positions, training_data = fh.load_training_data(training_data_filepath, windows=True)


    def predict_position(self,rssi_measurement, k=3):
        sorted_points = sorted(list(rssi_measurement.items()), key = lambda p : p[1],reverse=True)
        first_k = sorted_points[:k]

        position = np.zeros(2)

        rssi_sum = sum([rssi for _, rssi in first_k])
        for beacon, rssi in first_k:
            position += (rssi / rssi_sum) * self.beacon_positions[beacon]

        return position



class PropagationModel(BaseModel):

    def __init__(self, training_data_filepath: Path, n):
        self.beacon_positions, training_data = fh.load_training_data(training_data_filepath, windows=True)
        training_data = process_training_data(training_data,type = const.MeasurementProcess.MEAN) 

        #get constant values closest to 1
        beacon_constants = {}
        for beacon,data in training_data.items():
            beacon_position = self.beacon_positions[beacon]
            distances = np.linalg.norm(data[:,1:]-beacon_position,axis=1) - 1
            closest_index = np.argmin(distances)
            beacon_constants[beacon] = (data[closest_index,0], 1+distances[closest_index])


        self.distance_functions = {}
        for beacon, constants in beacon_constants.items():
            self.distance_functions[beacon] = lambda rssi : constants[1]*np.power((rssi-constants[0])/-10*n,10)


    def predict_position(self, rssi_measurement):

        distance_sum = 1*10**-6
        beacon_distances = {}
        for beacon, measurement in rssi_measurement.items():
            distance = self.distance_functions[beacon](measurement)
            distance_sum+= distance
            beacon_distances[beacon] = distance

        
        position = np.zeros(2)

        for beacon,distance in beacon_distances.items():
            position += (distance/ distance_sum) * self.beacon_positions[beacon]

        return position

        


