#!/usr/bin/env python

import time

# Mission Phase
mission_state = 'IDLE'  # IDLE, FLIGHT_SETUP, PUSHER_CHECK, READY, PUSH, COAST, BRAKE, SPINDOWN, POD_SAFE, EGRESS, FAULT/ABORT

# Hover Engine
he_state = 'OFF'  # OFF, STARTING, RUNNING, SHUTDOWN, EMERGENCY_SHUTDOWN
he_target_state = 'OFF'


def process():
    process_mission_phase()
    process_hover_engines()
    # ...

def process_mission_phase():
    
    # @TODO: Handle pod stop command
    
    # @todo: maybe have startup/reset state? 
    
    if mission_state == 'IDLE':
        # Pod must be totally idle in this state. No chance of movement or anything that could cause injury. (@todo: maybe use POD_SAFE here?)

        # NOTE: Can transition to FAULT
        
        # Exit criteria
        
        # Test mode (@todo: do we need an interlock, or just a command?)
        if test_mode_interlock_unlocked():
            if test_mode_interlock_execute():
                mission_state = 'TEST_MODE'

        # Flight setup interlock condition (1 packet to enable transition, another to activate it)
        if flight_setup_interlock_unlocked():
            if flight_setup_interlock_execute():
                mission_state = 'FLIGHT_SETUP'

        # Shutdown
        if shutdown_interlock_unlocked():
            if shutdown_interlock_execute():
                mission_state = 'SHUTDOWN'
    
    elif mission_state == 'TEST_MODE':
        # Allow manual (and automated) tests to be run on the pod
        
        if exit_test_mode_cmd():
            mission_state = 'IDLE'

        # Note: if things get too hot during test mode, or the brakes aren't retracted or something, you 
        # can transition to flight setup but you'll fail the tests_passed() and won't be able to move foreward to push 
    
    elif mission_state == 'FLIGHT_SETUP':
        # - (Probably a mostly manual process in practice)
        # - Cooling system on/enabled
        # - Retract brakes/ensure retracted
        # - Start hovering (NOTE: we only have so much battery, we heat up the subtrack and the engines, etc. -- trans to FAULT if we hold in FLIGHT_SETUP too long after hover start)
            # Probably set a timer (e.g. 1:30 )

            # Set a flag to indicate that the hover engines should start up
            he_target_state = 'RUNNING'
        # - Landing gear up
        # - Networking connected
        # - (other subsystems?)
        # - If not ^, FAULT/ABORT

        # NOTE: Can transition to FAULT
        #   - if we levitate for too long before transitioning to PUSHER_CHECK
        
        # Exit criteria
        # @todo: any other way out of FLIGHT_SETUP? Fault only? Spindown? 
        if tests_passed() and brakes_retracted() and pusher_interlock_confirmed() and manual_ready_cmd():
            mission_state = 'READY'
        
    elif mission_state == 'READY':

        # @TODO: interlock to exit in case of, say, spacex error/delay? Will that be allowed? What do we do in the case that the pusher fails? 
            # No timeouts allowed? 
            # Don't want to hover too long (can't, in fact)
        
        # NOTE: CAN NOT transition to FAULT. Can raise faults -- how do we handle those in the case that push has not started? (see above)
        
        # Exit criteria
        # Note: These are the ONLY conditions for moving from the ready state to the push state
        if accel_confirmed():
            mission_state = 'PUSH'
            start_push_timer()  # We can't brake until this times out
    
    elif mission_state == 'PUSH':
        
        # Handle any faults -- we have to make decisions to keep the pod in the best/safest state possible since manual control (except pod stop) is unlikely
        
        # If the hover engines haven't started up properly when the push starts, shut them down NOW
        if hover_engine_fault() or he_state != 'RUNNING':
            he_target_state = "EMERGENCY_SHUTDOWN"  # We have to deal with faults on the fly in PUSH, COAST, and BRAKE

        # Exit criteria
        if push_timer_expired() and pusher_separation_confirmed():
            mission_state = 'COAST'
            start_coast_timer()
            
    elif mission_state == 'COAST':
        
        # Exit criteria
        if coast_timer_expired():
            mission_state = 'BRAKE'

    elif mission_state == 'BRAKE':
        # Delegate to brake controller (PID, dead man's switch, etc.)
        # ...
        
        # Exit criteria
        if stopped_after_braking():  # What if we don't detect stop? Is that possible? Do we need another backstop? 
            mission_state = 'SPINDOWN'
            
    elif mission_state == 'SPINDOWN':
        # Deactivate hover engines, blast things with CO2, power down, make safe
        # ...
        
        # NOTE: Can transition to FAULT (e.g. if a relay gets stuck or something -- need to indicate that it's not safe to approach)
        
        # @TODO: what happens if we don't successfully shut everything down? 
        
        if spindown_complete():  # Maybe have a general function for checking pod safety? Might want to use that elsewhere (e.g. on startup)
            mission_state = 'POD_SAFE'

    elif mission_state == 'POD_SAFE':
        # @TODO: Handle interlock command
        # ...

        # NOTE: Can transition to FAULT

        # Exit criteria
        if pod_safe_interlock_unlocked():
            if pod_safe_interlock_execute():
                # @todo: are there any other states we can transition to? How do we control that if we want to? 
                mission_state = 'EGRESS'

    elif mission_state == 'EGRESS':
        # Handle egress commands (clutch, drive, etc.)

        # NOTE: Can transition to FAULT

        # Exit conditions
        if manual_idle_command():
            mission_state = 'IDLE'

    elif mission_state == 'SHUTDOWN':
        # Shut down the pod. This is the final state.
        
        # (power is off now)

    else:
        raise Exception("How did we get here?!?")
    

def process_hover_engines():
    
    # Check for faults
    
    if he_state == 'OFF':
        if he_target_state == 'RUNNING':
            # Check conditions for starting hover engines
            pass
            # If ok, change to STARTING 
            he_state = 'STARTING'
    elif he_state == 'STARTING':
        # Execute startup sequence
        pass

        if he_startup_complete():
            he_state = 'RUNNING'

    elif he_state == 'RUNNING':
        pass  
        # Not much to do
        # Note: other things can change our state
    elif he_state == 'SHUTDOWN':
        # Execute shutdown sequence and mark complete once finished
        pass
        
        if shutdown_sequence_complete:
            shutdown_sequence_complete = False
            he_state = 'OFF'
        
    elif he_state == 'EMERGENCY_SHUTDOWN':
        # CUT POWER TO THE HOVER ENGINES NOW
        pass
        he_state = 'OFF'

    else:
        raise Exception("We shouldn't be here...")

        
while True:
    
    process()
    process_hover_engines()
    time.wait(0.01)
    