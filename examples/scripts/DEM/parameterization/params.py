'''
Created on July 9, 2016
@author: Andrew Abi-Mansour
'''

# !/usr/bin/python
# -*- coding: utf8 -*-

from PyGran import Simulator, Analyzer, Visualizer
from PyGran.Materials import organic


# Launch 4 simultaneous simulations, each different coef of rest
nSim = 4
materials = [organic.copy() for i in range(nSim)]

for i, mat in enumerate(materials):
	mat['coefficientRestitution'] = 0.9 / (1 + i)

# Create a dictionary of physical parameters
params = {

	# Define the system
	'boundary': ('p','p','f'), # fixed BCs
	'box':  (-0.001, 0.001, -0.001, 0.001, 0, 0.004), # simulation box size

	# Define component(s)
	'SS': ({'material': materials, 'radius': ('constant', 2e-4)}, 
		),

	# Timestep
	'dt': 2e-6,

	# Apply gravitional force in the negative direction along the z-axis
	'gravity': (9.81, 0, 0, -1),

	# Number of simulation steps (non-PyGran variable)
	'nsteps': 1e3,

	# Number of concurrent simulations to run
	'nSim': nSim
}

if __name__ == '__main__':

	# Create an instance of the DEM class
        sim = Simulator.DEM(**params)

	# Setup a primitive wall along the xoy plane at z=0
	sim.setupWall(species=1, wtype='primitive', plane = 'zplane', peq = 0.0)

	# Insert the particles
	insert = sim.insert(species=1, value=100, region=('block', -1e-3,1e-3, -1e-3, 1e-3, 0, 3e-3))
	sim.run(params['nsteps'], params['dt'])
	sim.remove(insert)

	# Relax the system
	sim.run(params['nsteps'], params['dt'])