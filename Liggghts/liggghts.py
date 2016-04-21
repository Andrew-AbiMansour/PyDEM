#   Author: Andrew Abi-Mansour
#   Python wrapper for LIGGGHTS library via ctypes
#
# ----------------------------------------------------------------------
#
#   Modified from  LAMMPS source code
#   LAMMPS - Large-scale Atomic/Molecular Massively Parallel Simulator
#   http://lammps.sandia.gov, Sandia National Laboratories
#   Steve Plimpton, sjplimp@sandia.gov
#
#   Copyright (2003) Sandia Corporation.  Under the terms of Contract
#   DE-AC04-94AL85000 with Sandia Corporation, the U.S. Government retains
#   certain rights in this software.  This software is distributed under 
#   the GNU General Public License.
#
#   See the README file in the top-level LAMMPS directory.
#
# -------------------------------------------------------------------------

import sys,traceback,types
from ctypes import *
from os.path import dirname, abspath, join
from inspect import getsourcefile

import numpy as np
import itertools
import logging
from numpy.linalg import norm
from scipy import spatial
from mpi4py import MPI
import os
import matplotlib.pylab as plt
import glob
import sys

logging.basicConfig(filename='dem.log', format='%(asctime)s:%(levelname)s: %(message)s', level=logging.DEBUG)

class liggghts:
  # detect if Python is using version of mpi4py that can pass a communicator
  
  has_mpi4py_v2 = False
  try:
    from mpi4py import MPI
    from mpi4py import __version__ as mpi4py_version
    if mpi4py_version.split('.')[0] == '2':
      has_mpi4py_v2 = True
  except:
    pass

  # create instance of LIGGGHTS
 
  def __init__(self,name="",cmdargs=None,ptr=None,comm=None):

    # determine module location
    
    modpath = dirname(abspath(getsourcefile(lambda:0)))

    # load libliggghts.so unless name is given.
    # e.g. if name = "g++", load libliggghts_g++.so
    # try loading the LIGGGHTS shared object from the location
    # of liggghts.py with an absolute path (so that LD_LIBRARY_PATH
    # does not need to be set for regular installations.
    # fall back to loading with a relative path, which typically
    # requires LD_LIBRARY_PATH to be set appropriately.

    try:
      if not name: 
	cwd = os.getcwd()
	self.lib = CDLL(join(modpath,"{}/Liggghts/libliggghts.so".format(cwd)),RTLD_GLOBAL)
      else: self.lib = CDLL(join(modpath,"{}/Liggghts/libliggghts_{}.so".format(cwd, name)),RTLD_GLOBAL)
    except:
      if not name: self.lib = CDLL("{}/Liggghts/libliggghts.so".format(cwd), RTLD_GLOBAL)
      else: self.lib = CDLL("{}/Liggghts/libliggghts_{}.so".format(cwd,name), RTLD_GLOBAL)

    # if no ptr provided, create an instance of LIGGGHTS
    #   don't know how to pass an MPI communicator from PyPar
    #   but we can pass an MPI communicator from mpi4py v2.0.0 and later
    #   no_mpi call lets LIGGGHTS use MPI_COMM_WORLD
    #   cargs = array of C strings from args
    # if ptr, then are embedding Python in LIGGGHTS input script
    #   ptr is the desired instance of LIGGGHTS
    #   just convert it to ctypes ptr and store in self.lmp
    
    if not ptr:
      # with mpi4py v2, can pass MPI communicator to LIGGGHTS
      # need to adjust for type of MPI communicator object
      # allow for int (like MPICH) or void* (like OpenMPI)
      
      if liggghts.has_mpi4py_v2 and comm != None:
        if liggghts.MPI._sizeof(liggghts.MPI.Comm) == sizeof(c_int):
          MPI_Comm = c_int
        else:
          MPI_Comm = c_void_p

        narg = 0
        cargs = 0
        if cmdargs:
          cmdargs.insert(0,"liggghts.py")
          narg = len(cmdargs)
          cargs = (c_char_p*narg)(*cmdargs)
          self.lib.liggghts_open.argtypes = [c_int, c_char_p*narg, \
                                           MPI_Comm, c_void_p()]
        else:
          self.lib.liggghts_open.argtypes = [c_int, c_int, \
                                           MPI_Comm, c_void_p()]

        self.lib.liggghts_open.restype = None
        self.opened = 1
        self.lmp = c_void_p()
        comm_ptr = liggghts.MPI._addressof(comm)
        comm_val = MPI_Comm.from_address(comm_ptr)
        self.lib.liggghts_open(narg,cargs,comm_val,byref(self.lmp))

      else:
        self.opened = 1
        if cmdargs:
          cmdargs.insert(0,"liggghts.py")
          narg = len(cmdargs)
          cargs = (c_char_p*narg)(*cmdargs)
          self.lmp = c_void_p()
          self.lib.liggghts_open_no_mpi(narg,cargs,byref(self.lmp))
        else:
          self.lmp = c_void_p()
          self.lib.lammps_open_no_mpi(0,None,byref(self.lmp))
          # could use just this if LIGGGHTS lib interface supported it
          # self.lmp = self.lib.lammps_open_no_mpi(0,None)
          
    else:
      self.opened = 0
      # magic to convert ptr to ctypes ptr
      pythonapi.PyCObject_AsVoidPtr.restype = c_void_p
      pythonapi.PyCObject_AsVoidPtr.argtypes = [py_object]
      self.lmp = c_void_p(pythonapi.PyCObject_AsVoidPtr(ptr))

  def __del__(self):
    if self.lmp and self.opened: self.lib.lammps_close(self.lmp)

  def close(self):
    if self.opened: self.lib.lammps_close(self.lmp)
    self.lmp = None

  def version(self):
    return self.lib.lammps_version(self.lmp)

  def file(self,file):
    self.lib.lammps_file(self.lmp,file)

  def command(self,cmd):
    self.lib.lammps_command(self.lmp,cmd)

  def extract_global(self,name,type):
    if type == 0:
      self.lib.lammps_extract_global.restype = POINTER(c_int)
    elif type == 1:
      self.lib.lammps_extract_global.restype = POINTER(c_double)
    else: return None
    ptr = self.lib.lammps_extract_global(self.lmp,name)
    return ptr[0]

  def extract_atom(self,name,type):
    if type == 0:
      self.lib.lammps_extract_atom.restype = POINTER(c_int)
    elif type == 1:
      self.lib.lammps_extract_atom.restype = POINTER(POINTER(c_int))
    elif type == 2:
      self.lib.lammps_extract_atom.restype = POINTER(c_double)
    elif type == 3:
      self.lib.lammps_extract_atom.restype = POINTER(POINTER(c_double))
    else: return None
    ptr = self.lib.lammps_extract_atom(self.lmp,name)
    return ptr

  def extract_compute(self,id,style,type):
    if type == 0:
      if style > 0: return None
      self.lib.lammps_extract_compute.restype = POINTER(c_double)
      ptr = self.lib.lammps_extract_compute(self.lmp,id,style,type)
      return ptr[0]
    if type == 1:
      self.lib.lammps_extract_compute.restype = POINTER(c_double)
      ptr = self.lib.lammps_extract_compute(self.lmp,id,style,type)
      return ptr
    if type == 2:
      self.lib.lammps_extract_compute.restype = POINTER(POINTER(c_double))
      ptr = self.lib.lammps_extract_compute(self.lmp,id,style,type)
      return ptr
    return None

  # in case of global datum, free memory for 1 double via lammps_free()
  # double was allocated by library interface function
  
  def extract_fix(self,id,style,type,i=0,j=0):
    if style == 0:
      self.lib.lammps_extract_fix.restype = POINTER(c_double)
      ptr = self.lib.lammps_extract_fix(self.lmp,id,style,type,i,j)
      result = ptr[0]
      self.lib.lammps_free(ptr)
      return result
    elif (style == 1) or (style == 2):
      if type == 1:
        self.lib.lammps_extract_fix.restype = POINTER(c_double)
      elif type == 2:
        self.lib.lammps_extract_fix.restype = POINTER(POINTER(c_double))
      else:
        return None
      ptr = self.lib.lammps_extract_fix(self.lmp,id,style,type,i,j)
      return ptr
    else:
      return None

  # free memory for 1 double or 1 vector of doubles via lammps_free()
  # for vector, must copy nlocal returned values to local c_double vector
  # memory was allocated by library interface function
  
  def extract_variable(self,name,group,type):
    if type == 0:
      self.lib.lammps_extract_variable.restype = POINTER(c_double)
      ptr = self.lib.lammps_extract_variable(self.lmp,name,group)
      result = ptr[0]
      self.lib.lammps_free(ptr)
      return result
    if type == 1:
      self.lib.lammps_extract_global.restype = POINTER(c_int)
      nlocalptr = self.lib.lammps_extract_global(self.lmp,"nlocal")
      nlocal = nlocalptr[0]
      result = (c_double*nlocal)()
      self.lib.lammps_extract_variable.restype = POINTER(c_double)
      ptr = self.lib.lammps_extract_variable(self.lmp,name,group)
      for i in xrange(nlocal): result[i] = ptr[i]
      self.lib.lammps_free(ptr)
      return result
    return None

  # set variable value
  # value is converted to string
  # returns 0 for success, -1 if failed
  
  def set_variable(self,name,value):
    return self.lib.lammps_set_variable(self.lmp,name,str(value))

  # return total number of atoms in system
  
  def get_natoms(self):
    return self.lib.lammps_get_natoms(self.lmp)

  # return vector of atom properties gathered across procs, ordered by atom ID

  def gather_atoms(self,name,type,count):
    natoms = self.lib.lammps_get_natoms(self.lmp)
    if type == 0:
      data = ((count*natoms)*c_int)()
      self.lib.lammps_gather_atoms(self.lmp,name,type,count,data)
    elif type == 1:
      data = ((count*natoms)*c_double)()
      self.lib.lammps_gather_atoms(self.lmp,name,type,count,data)
    else: return None
    return data

  # scatter vector of atom properties across procs, ordered by atom ID
  # assume vector is of correct type and length, as created by gather_atoms()

  def scatter_atoms(self,name,type,count,data):
    self.lib.lammps_scatter_atoms(self.lmp,name,type,count,data)

class DEMPy:
  """A class that implements a python interface for DEM computations"""

  def __init__(self, rank, split, units, dim, style, **pargs):
    """ Initialize some settings and specifications 
    @ units: unit system (si, cgs, etc.)
    @ dim: dimensions of the problem (2 or 3)
    # style: granular, atom, or ...
    """
    self.rank = rank

    if not self.rank:
      logging.info('Instantiating LIGGGHTS object')
     
    self.lmp = liggghts(comm=split)
    self.pargs = pargs
    self.monitorList = []
    self.vars = []

    if not self.rank:
      logging.info('Setting up problem dimensions and boundaries')

    self.lmp.command('units {}'.format(units))
    self.lmp.command('dimension {}'.format(dim))
    self.lmp.command('atom_style {}'.format(style))
    self.lmp.command('atom_modify map array') # array is faster than hash in looking up atomic IDs, but the former takes more memory
    self.lmp.command('boundary {} {} {}'.format(*pargs['boundary']))
    self.lmp.command('newton off') # turn off newton's 3rd law ~ should lead to better scalability
    self.lmp.command('communicate single vel yes') # have no idea what this does, but it's imp for ghost atoms
    self.lmp.command('processors * * *') # let LIGGGHTS handle DD

    if not self.rank:
      logging.info('Creating i/o directories')

      if not os.path.exists(self.pargs['traj'][2]):
        os.makedirs(self.pargs['traj'][2])

      if not os.path.exists(self.pargs['restart'][1]):
        os.makedirs(self.pargs['restart'][1])

  def createDomain(self):
    """ Define the domain of the simulation
    @ nsys: number of subsystems
    @ pos: 6 x 1 tuple that defines the boundaries of the box 
    """
    if not self.rank:
      logging.info('Creating domain')

    self.lmp.command('region domain block {} {} {} {} {} {} units box'.format(*self.pargs['box']))
    self.lmp.command('create_box {} domain'.format(self.pargs['nSS'] + 1))

  def insertParticles(self):
    """ Create atoms in a pre-defined region
    @ N: max total number of particles to be inserted
    @ density: initial density of the particles
    @ vel: 3 x 1 tuple of initial velocities of all particles
    @ args: dictionary of params
    """
    if not self.rank:
      logging.info('Inserting particles')

    for ss in range(self.pargs['nSS']):
    
      radius = self.pargs['radius'][ss]
      density = self.pargs['density'][ss]

      self.lmp.command('fix pts all particletemplate/sphere 1 atom_type 1 density constant {} radius'.format(density) + (' {}' * len(radius)).format(*radius))
      self.lmp.command('fix pdd all particledistribution/discrete 63243 1 pts 1.0')
  
      self.lmp.command('region factory sphere 0 0.6 0 0.4 units box')
      self.lmp.command('fix ins all insert/rate/region seed 123481 distributiontemplate pdd nparticles {} particlerate {} insert_every {} overlapcheck yes vel constant {} {} {} region factory ntry_mc 1000'.format(self.pargs['Natoms'][ss], self.pargs['insertRate'][ss], self.pargs['insertFreq'][ss], *self.pargs['vel'][ss]))
      #self.lmp.command('fix myInsRate all insert/rate/region seed 123481 distributiontemplate pdd \
       #nparticles {} particlerate {} insert_every {} \
       #overlapcheck yes vel constant {} region factory ntry_mc 10000'.format(self.pargs['Natoms'][ss], self.pargs['insertRate'][ss], self.pargs['insertFreq'][ss], \
       #*self.pargs['vel'][ss]))

  def importMesh(self, name):
    """
    """
    fname = self.pargs['mesh']

    if not self.rank:
      logging.info('importing mesh from {}'.format(fname))

    self.lmp.command('fix {} all mesh/surface file {} type 2 scale {}'.format(name, fname, self.pargs['scaleMesh']))

  def setupWall(self, name, wtype, plane = None, peq = None):
    """
    Creates a wall
    @ name: name of the variable defining a wall or a mesh
    @ wtype: type of the wall (primitive or mesh)
    @ plane: x, y, or z plane for primitive walls
    @ peq: plane equation for primitive walls
    """

    if wtype == 'mesh':
      self.lmp.command('fix myMesh all wall/gran model hooke {} n_meshes 1 meshes {}'.format(wtype, name))
    elif wtype == 'primitive':
      self.lmp.command('fix {} all wall/gran model hooke {} type 1 {} {}'.format(name, wtype, plane, peq))
    else:
      raise ValueError('Wall type can be either primitive or mesh')

  def remove(self, name):
    """
    Deletes a specified variable
    """
    self.lmp.command('unfix {}'.format(name))

  def createGroup(self, group = None):
    """ Create groups of atoms 
    """
    if not self.rank:
      logging.info('Creating atom group {}'.format(group))

    if group is None:
      for idSS in self.pargs['idSS']:
        self.lmp.command('group group{} type {}'.format(idSS, idSS))

  def setupNeighbor(self):
    """
    """
    if not self.rank:
      logging.info('Setting up nearest neighbor searching parameters')

    self.lmp.command('neighbor 0.001 bin')
    self.lmp.command('neigh_modify delay 0')

  def createProperty(self, name, *args):
    """
    Material and interaction properties required
    """
    if not self.rank:
      logging.info('Creating proprety {} with args'.format(name) + (' {}' * len(args)).format(*args))

    self.lmp.command('fix {} all property/global'.format(name) + (' {}' * len(args)).format(*args))

  def setupPhysics(self):
    """
    Specify the interation forces
    """
    if not self.rank:
      logging.info('Setting up interaction parameters')

    args = self.pargs['model']

    self.lmp.command('pair_style ' + (' {}' * len(args)).format(*args))
    self.lmp.command('pair_coeff * *')

  def setupGravity(self):
    """
    Specify in which direction the gravitational force acts
    """
    self.lmp.command('fix myGravity all gravity {} vector {} {} {}'.format(*self.pargs['gravity']))

  def initialize(self):
    """
    """

    self.lmp.command('restart {} {}/{}'.format(*self.pargs['restart']))

    if self.pargs['restart'][-1] == False:

      self.createDomain()
      #self.createGroup()
      self.setupPhysics()
      self.setupNeighbor()
      self.insertParticles()
      self.setupGravity()

    else:
      self.resume()
      self.setupPhysics()
      self.setupNeighbor()

  def setupIntegrate(self, name, dt = None):
    """
    Specify how Newton's eqs are integrated in time. 
    @ name: name of the fixed simulation ensemble applied to all atoms
    @ dt: timestep
    @ ensemble: ensemble type (nvt, nve, or npt)
    @ args: tuple args for npt or nvt simulations
    """
    if not self.rank:
      logging.info('Setting up integration scheme parameters')

    self.lmp.command('fix {} all nve/sphere'.format(name))

    if dt is None:
      self.lmp.command('timestep {}'.format(self.pargs['dt']))

  def integrate(self, steps):
    """
    Run simulation in time
    """
    if not self.rank:
      logging.info('Integrating the system for {} steps'.format(steps))

    self.lmp.command('run {}'.format(steps))

    for tup in self.monitorList:
      self.lmp.command('compute {} {} {}'.format(*tup))
      self.vars.append(self.lmp.extract_compute(tup[0], 0, 0))
      self.lmp.command('uncompute {}'.format(tup[0]))

  def printSetup(self, freq):
    """
    Specify which variables to write to file, and their format
    """
    if not self.rank:
      logging.info('Setting up printing options')

    args = self.pargs['print']
    self.lmp.command('thermo_style custom' + (' {}' * len(args)).format(*args))
    self.lmp.command('thermo {}'.format(freq))
    self.lmp.command('thermo_modify norm no lost ignore')

  def dumpSetup(self):
    """
    """
    if not self.rank:
      logging.info('Setting up trajectory i/o')

    traj, trajFormat = self.pargs['traj'][-1].split('.')

    self.lmp.command('dump dump {} {} {} {}/{}'.format(self.pargs['traj'][0], trajFormat, self.pargs['traj'][1], self.pargs['traj'][2],  self.pargs['traj'][-1]))

  def extractCoords(self, coords):
    """
    Extracts atomic positions from a certian frame and adds it to coords
    """
    # Extract coordinates from liggghts
    self.lmp.command('variable x atom x')
    x = Rxn.lmp.extract_variable("x", "group1", 1)

    self.lmp.command('variable y atom y')
    y = Rxn.lmp.extract_variable("y", "group1", 1)

    self.lmp.command('variable z atom z')
    z = Rxn.lmp.extract_variable("z", "group1", 1)

    for i in range(Rxn.lmp.get_natoms()):
      coords[i,:] += x[i], y[i], z[i]

    self.lmp.command('variable x delete')
    self.lmp.command('variable y delete')
    self.lmp.command('variable z delete')

    return coords

  def monitor(self, name, group, var):
    """
    """
    self.monitorList.append((name, group, var))

  def plot(self, name, xlabel, ylabel, output=None):
    """
    """
    plt.rc('text', usetex=True)
    time = np.array(range(len(sim.vars))) * self.pargs['traj'][1] * self.pargs['dt']

    plt.plot(time, sim.vars)
    plt.xlabel(r"{}".format(xlabel))
    plt.ylabel(ylabel)

    if output is not None:
      plt.savefig(output)

  def resume(self):
    """
    """
    rdir = '{}/*'.format(self.pargs['restart'][1])
    rfile = max(glob.iglob(rdir), key=os.path.getctime)

    self.lmp.command('read_restart {}'.format(rfile))

  def __del__(self):
    """ Destructor
    """
    self.lmp.close()

    if self.pargs['clean'] == True:
	os.system('rm -r restart/ traj/ *.log log.*')

class DEM:
  """A clss that handles communication for the DEM object"

  def __init__(self, nSim, **pargs):
    """ Initialize COMM and partition proccesors based on user input """

    self.comm = MPI.COMM_WORLD
    self.rank = self.comm.Get_rank()
    nProcs = self.comm.Get_size()

    if not self.rank:
      logging.info("Initializing MPI for a total of %d procs" % (self.comm.Get_size()))

    nPart = nProcs // nSim

    if nSim > 1:
      logging.info('Running {} simulations: multi-mode on'.format(nSim))

    self.dem = []

    for i in range(nSim):
      if self.rank < nPart * (i + 1):
        self.color = i
        self.split = self.comm.Split(self.color, key=0)

        dem.append(DEMPy(self.rank, self.split, **pargs))           
        break

   def __del__(self):

     MPI.Finalize()
	
