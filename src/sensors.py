#!/usr/bin/env python

#!/usr/bin/env python
# coding=UTF-8

# File:     sensors.py
# Purpose:  Sensor classes
# Author:   Ryan Adams (@ninetimeout)
# Date:     2016-Dec-17

# NOTE: Please add your name to 'Author:' if you work on this file. Thanks!

# Note: all units are SI: meters/s^2, meters/s, and meters. Time is in microseconds (?)
import logging
import numpy as np
from units import Units
from collections import deque

# @see https://scimusing.wordpress.com/2013/10/25/ring-buffers-in-pythonnumpy/
# RDA: modified to work with any dtype
class RingBuffer():
    "A 1D ring buffer using numpy arrays"
    def __init__(self, length, dtype='f'):
        self.data = np.zeros(length, dtype=dtype)
        self.index = 0

    def extend(self, x):
        "adds array x to ring buffer"
        if x.size:
            x_index = (self.index + np.arange(x.size)) % self.data.size
            self.data[x_index] = x
            self.index = x_index[-1] + 1

    def get(self):
        "Returns the first-in-first-out data in the ring buffer"
        idx = (self.index + np.arange(self.data.size)) %self.data.size
        return self.data[idx]

"""
def ringbuff_numpy_test():
    ringlen = 100000
    ringbuff = RingBuffer(ringlen)
    for i in range(40):
        ringbuff.extend(np.zeros(10000, dtype='f')) # write
        ringbuff.get() #read
"""

class PollingSensor:
    """ Sensor that provides a data stream  """
    
    """
    Note: Sensors will need inputs from the outside world -- sensors will need to 'sample' the world. 
          - How do we connect a sensor to what it needs to measure? In the constructor? 
          - Probably want an id as well for logging purposes.
    
    
    """

    def __init__(self, sim, config):
        
        self.sim = sim
        self.config = config
        self.logger = logging.getLogger("PollingSensor")

        # Configuration

        # Grab the fixed timestep from the sim. If we wanted to use a variable timestep we would need to do the next calculations in the lerp function
        self.fixed_timestep = Units.SI(self.sim.config.fixed_timestep)
        self.sampling_rate = Units.SI(self.config.sampling_rate)  # Hz

        # @see self._add_noise() and numpy.random.normal
        self.noise_center = self.config.noise_center or 0.0
        self.noise_scale = self.config.noise_scale or 0.0

        # Volatile
        #self.buffer = RingBuffer(config.buffer_size, config.dtype)   # @todo: How to specify dtype in configuration? There should be a string rep of dtype I think 
        self.buffer = deque()
        self.next_start = 0.0
        self.step_lerp_pcts = None  # Set during step
        
    def create_step_samples(self):
        """ Get the step samples """
        pass  # Deferred to subclasses

        """ Example using pod height:
        start_value = self.sim.pod.last_height
        end_value = self.sim.pod.height

        # Lerp values to get samples
        samples = start_value + self.step_lerp_pcts * (end_value - start_value)  # Or use self.lerp(start_value, end_value), but doing it directly is faster since no function call
        if self.noise_scale > 0:
            # Add gaussian noise if specified
            return samples + np.random.normal(0.0, noise_scale, len(samples))
        else:
            # No noise
            return samples          
        """
    
    def step(self, dt_usec):
        # @todo: what do we do here? Just update next_start? Get samples and do something with them? 
        if self.next_start >= 1:
            self.next_start -= 1
            return
        
        samples_per_step = self.sampling_rate * dt_usec / 1000000.
        sample_pct_of_step = 1.0/samples_per_step  # For lerping

        self.step_lerp_pcts = np.arange(self.next_start, 1, sample_pct_of_step)

        # Call get_step_samples() (implemented in subclasses) to get the samples and add them to the buffer
        self.buffer.extend(self.create_step_samples())

        # Update or start pct for the next step
        self.next_start = sample_pct_of_step - (1 - self.step_lerp_pcts[-1])

    def pop(self):
        pass
        #return self.buffer.get()  # @todo: fix this to work with whatever data structure we use for the buffer
        
    def pop_all(self):
        out = np.array(self.buffer)
        self.buffer.clear()
        return out
    
    # Helper methods
        
    def _lerp(self, start_value, end_value):
        """ Lerp between the two values using the self.step_lerp_pcts vector and return a vector of lerp'd values """
        return start_value + self.step_lerp_pcts * (end_value - start_value)
    
    def _get_gaussian_noise(self, samples, noise_center=0.0, noise_scale=0.1):
        if noise_scale > 0:
            return np.random.normal(noise_center, noise_scale, len(samples))
        else:
            return 0


class LaserOptoSensor(PollingSensor):
    
    def __init__(self, sim, config):
        PollingSensor.__init__(self, sim, config)  # @todo: is this right? 
        self.logger = logging.getLogger("LaserOptoSensor")
        
        # Get the height offset for this sensor?
        pass

    def create_step_samples(self):
        # Create height samples
        height_samples = self._lerp(self.sim.pod.last_height, self.sim.pod.height)
        
        # Add noise. @todo: we might want to do this after we adjust for gaps? 
        height_samples += self._get_gaussian_noise(height_samples, self.noise_center, self.noise_scale)
        
        # Gap positions
        # Pod positioning so that we can check for gap traversal
        pod_start_pos = self.sim.pod.last_position
        pod_end_pos = self.sim.pod.position

        gaps = np.array(self.sim.tube.track_gaps)

        gap_indices_in_step_range = np.nonzero(np.logical_and(gaps >= pod_start_pos, gaps <= pod_end_pos))[0]  # [0] because np.nonzero deals with n dimensions, but we only have one
        #self.logger.debug("Gap indices in step range {} to {}: {}".format(pod_start_pos, pod_end_pos, gap_indices_in_step_range))
        gap_positions_in_step_range = np.array(gaps)[gap_indices_in_step_range]
        
        #self.logger.debug("Gap positions in step range: {}".format(gap_positions_in_step_range))
        
        # If we're traversing any gaps this step...
        if len(gap_positions_in_step_range):

            # Get the x position of each sample in this step to see if it is over a crack
            sample_positions = self._lerp(pod_start_pos, pod_end_pos)
            
            # Find the samples that are over a gap (if any)
            over_gap_indices = []  # Note: can't use a np array here since no extending
            for gap_start_pos in gap_positions_in_step_range:
                gap_end_pos = gap_start_pos + self.sim.tube.track_gap_width
                over_gap_indices.extend(np.nonzero(np.logical_and(sample_positions >= gap_start_pos, sample_positions <= gap_end_pos))[0].tolist())

            #self.logger.debug("Over gap indices: {}".format(over_gap_indices))

            # Adjust the samples that are over gaps
            if len(over_gap_indices) > 0:
                self._adjust_samples_for_gaps(height_samples, over_gap_indices)

        # Return our (possibly adjusted) height samples
        #self.logger.debug("Created {} samples".format(len(height_samples)))
        return height_samples
            
    def _adjust_samples_for_gaps(self, samples, indices):
        """ Adjust the samples at the given indices as if they were over a gap """
        samples[indices] += 50.48 # @todo: adjust appropriately to match data collected at test weekend

        
# ---------------------------
# Just notes/sketches below here        
        
        
class DataCollector:
    
    def __init__(self, sim, config):
        self.sim = sim
        self.config = config
    
    def step(self, dt_usec):
        pass  # Defer this to subclasses?
        """
        Might look like: 
        - value0 = self.last_height
        - value1 = self.height
        - samples = self.sensor.create_step_samples(value0, value1)
        - self.writers.write(samples.asbin())
        """
        


# Inherit from someone? 
class InterruptingSensor():
    """ A sensor that can call a function if it detects an event during a step """
    def __init__(self, sim, config):
        self.sim = sim
        self.config = config
        
    def step(self, dt_usec):
        """ Detect event(s) and call the callback if detected """
        """
        if some_event_happened: 
            self.callback(pin_state)  # Does it get pin state here? 
        """

    def set_pin_change_callback(self, fn):
        self.callback = fn
        
    


class SensorBuffer:
    """ Collects sensor values and manages their storage/filtering/redirecting? """

    def __init__(self, sim, config):
        pass



import random

class LaserDistanceSensor():
    
    def create_sample(self):
        # @todo: fix this up
        return 18.3 + random.random() * 0.01
                
        
class Accelerometer:
    
    def __init__(self, pod):
        self.pod = pod

        # Volatile
        self.fifo = deque()
        self.sample_overflow = 0.  # Our timestep won't always yield a clean number (e.g. 'we should take 8.6 samples for this dt_usec'. Store the remainder here.)
        
        # Configuration
        self.sampling_rate_hz = 800
        self.buffer_size = 32
        self.precision = 14  # 14 bits
        self.buffer_mode = "something"   # Circular? 
    
    def step(self, dt_usec):
        # Add samples to the buffer based on how much time has passed and our sampling rate
        n_samples = self.sample_overflow + self.sampling_rate_hz * dt_usec / 1000000.0
        self.sample_overflow = n_samples - int(n_samples)  # Save off the remainder
        n_samples = int(n_samples)  # Discard the remainder
        
        for i in xrange(n_samples):
            self.fifo.pushleft(self.create_sample())
        
    def create_sample(self):
        pass
        # sample = self.pod.acceleration + fuzzing?
        # return (x, y, z)
    
class AccelData:
    def __init__(self):
        """
        # @see eng-software-pod/FIRMWARE/PROJECT_CODE/LCCM655__RLOOP__FCU_CORE/ACCELEROMETERS/fcu__accel__ethernet.c
        //fault flags
        vNUMERICAL_CONVERT__Array_U32(pu8Buffer, u32MMA8451__Get_FaultFlags(u8Device));
        pu8Buffer += 4U;

        //X Raw
        vNUMERICAL_CONVERT__Array_S16(pu8Buffer, s16MMA8451_FILTERING__Get_Average(u8Device, AXIS_X));
        pu8Buffer += 2U;

        //Y Raw
        vNUMERICAL_CONVERT__Array_S16(pu8Buffer, s16MMA8451_FILTERING__Get_Average(u8Device, AXIS_Y));
        pu8Buffer += 2U;

        //Z Raw
        vNUMERICAL_CONVERT__Array_S16(pu8Buffer, s16MMA8451_FILTERING__Get_Average(u8Device, AXIS_Z));
        pu8Buffer += 2U;

        //X Accel
        vNUMERICAL_CONVERT__Array_F32(pu8Buffer, f32MMA8451_MATH__Get_GForce(u8Device, AXIS_X));
        pu8Buffer += 4U;

        //Y Accel
        vNUMERICAL_CONVERT__Array_F32(pu8Buffer, f32MMA8451_MATH__Get_GForce(u8Device, AXIS_Y));
        pu8Buffer += 4U;

        //Z Accel
        vNUMERICAL_CONVERT__Array_F32(pu8Buffer, f32MMA8451_MATH__Get_GForce(u8Device, AXIS_Z));
        pu8Buffer += 4U;

        //Pitch
        vNUMERICAL_CONVERT__Array_F32(pu8Buffer, f32MMA8451_MATH__Get_PitchAngle(u8Device));
        pu8Buffer += 4U;

        //Roll
        vNUMERICAL_CONVERT__Array_F32(pu8Buffer, f32MMA8451_MATH__Get_RollAngle(u8Device));
        pu8Buffer += 4U;
        
        """


        self.dtype = np.dtype([
                ('fault_flags', np.uint32),
                ('raw_x', np.int16),
                ('raw_y', np.int16),
                ('raw_z', np.int16),
                ('accel_x', np.float32),
                ('accel_y', np.float32),
                ('accel_z', np.float32),                
                ('pitch', np.float32),
                ('roll', np.float32),                
        ])
        
        self._accel_indices = [0, 4, 5, 6]
        
        self.data = np.array([(0, 0.1, 12, 1234, 0.12345678901234, 0.12345678901234, 0.12345678901234, 0.12345678901234, 0.12345678901234)], dtype=self.dtype)
        self.data['fault_flags'] = 0
        self.data['raw_x'] = 0.1
        self.data['raw_y'] = 12
        self.data['raw_z'] = 31929
        self.data['accel_x'] = 0.12345678901234
        self.data['accel_y'] = 0.23456789012345
        self.data['accel_z'] = 0.34567890123456
        self.data['pitch'] = 0.1000
        self.data['roll'] = 0.2000


        print len(self.data.tostring(order="C"))
                
    def pack_safeudp_full(self):
        return self.data.tostring(order="C")
        
    def pack_safeudp_cal(self):
        print self.data[0]
        
        return self.data[0].tostring()

class AccelData2:
    
    def __init__(self):
        self.dtype = np.dtype('uint32, int16, int16, int16, float32, float32, float32, float32, float32')
        self.data = np.array([(0, 1, 12, 1234, 0.12345678901234, 0.12345678901234, 0.12345678901234, 0.12345678901234, 0.12345678901234)], dtype=self.dtype)
        print np.asmatrix(self.data)


if __name__ == "__main__":

    ad2 = AccelData2()
    exit()
    
    ad = AccelData()
    print len(ad.pack_safeudp_full())
    print len(ad.pack_safeudp_cal())
    print ""
    
    dt_usec = 100002
    sensor = LaserDistanceSensor()
    sensor.sampling_rate_hz = 200
    for i in xrange(10):
        sensor.step(dt_usec)
        print len(sensor.fifo)
    