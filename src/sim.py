
from pod import Pod
from tube import Tube
from pusher import Pusher
#from fcu import fcu

import time
import logging
from units import *

class Sim:
    
    def __init__(self, config):
        self.logger = logging.getLogger("Sim")

        self.logger.info("Initializing simulation")
        
        self.config = config

        self.fixed_timestep_usec = Units.usec(config.fixed_timestep)  # Convert to usec

        self.pusher = Pusher(self, self.config.pusher)
        self.tube = Tube(self, self.config.tube)
        self.pod = Pod(self, self.config.pod)      
        #self.fcu = Fcu(self, self.config.fcu)  

        # Initial setup
        self.pusher.start_push()

        # Volatile
        self.elapsed_time_usec = 0
        self.n_steps_taken = 0
        
        # Simulator control
        self.end_listeners = []
        
        # Testing only
        from sensors import SensorConsoleWriter   # @todo: move this to the top once we're done testing
        from sensor_laser_opto import LaserOptoSensor, LaserOptoTestListener
        self.laser_opto_1 = LaserOptoSensor(self, self.config.sensors.laser_opto_1)
        #self.laser_opto_1.register_step_listener(SensorConsoleWriter())  # Write data directly to the console
        self.lotl = LaserOptoTestListener()
        self.laser_opto_1.add_step_listener(self.lotl) 

        from sensor_laser_contrast import LaserContrastSensor, LaserContrastTestListener
        self.laser_contrast_1 = LaserContrastSensor(self, self.config.sensors.laser_opto_1)
        self.lctl = LaserContrastTestListener()
        self.laser_contrast_1.add_step_listener(self.lctl)
        
    def step(self, dt_usec):        

        # Step the pusher first (will apply pressure and handle disconnection)
        self.pusher.step(dt_usec)

        # Step the pod (will handle all other forces and pod physics)
        self.pod.step(dt_usec)
        
        #self.fcu.step(dt_usec)
        self.laser_opto_1.step(dt_usec)
        #self.logger.debug(list(self.laser_opto_1.pop_all()))
        self.laser_contrast_1.step(dt_usec)
        
        self.elapsed_time_usec += dt_usec
        self.n_steps_taken += 1

    def run(self):
        self.logger.info("Starting simulation")
        
        finished = False
        sim_start_t = time.time()
        while(True):

            # Check our end listener(s) to see if we should end the simulation (e.g. the pod has stopped)
            for listener in self.end_listeners:
                if listener.is_finished(self):
                    finished = True
            
            if finished:
                break
            
            self.step(self.fixed_timestep_usec)

        sim_end_t = time.time()
        sim_time = sim_end_t - sim_start_t
        print "LaserOptoTestListener: gap sensor took {} samples that were within a gap.".format(self.lotl.n_gaps)
        print "Simulated {} steps/{} seconds in {} actual seconds.".format(self.n_steps_taken, self.elapsed_time_usec/1000000, sim_time)
        
        
    def add_end_listener(self, listener):
        """ Add a listener that will tell us if we should end the simulator """
        self.end_listeners.append(listener)
        

class SimEndListener(object):

    def __init__(self):
        self.logger = logging.getLogger("SimEndListener")
        
    def is_finished(self, sim):

        # Check to see if we should end the sim

        # If we've stopped (after being pushed)
        if sim.pod.velocity >= 0:
            self.pushed = True  # set pushed to true when we've moved some
        elif self.pushed == True:  # Next time around, if we've been pushed, check to see if we've stopped.
            if sim.pod.velocity <= 0:
                self.logger.info("Ending simulation because reasons")
                return True

        # If we've hit the wall...
        if sim.pod.position >= sim.tube.length:
            self.logger.info("Pod has destroyed the tube and everything within a 10 mile radius.")
            return True

        return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    from config import *

    import pprint
    
    import argparse
    parser = argparse.ArgumentParser(description="rPod Simulation")
    parser.add_argument('configfile', metavar='config', type=str, nargs='+', default="None",
        help='Simulation configuration file(s) -- later files overlay on previous files')
    args = parser.parse_args()

    sim_config = Config()
    for configfile in args.configfile:
        sim_config.loadfile(configfile)
    
    pprint.pprint(sim_config)
    
    # print sim_config.sim.world.tube.length

    sim = Sim(sim_config.sim)

    sim.add_end_listener(SimEndListener())
    
    sim.run()

        
