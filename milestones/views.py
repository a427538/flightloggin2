from annoying.decorators import render_to

V = '<span class="v">&#10003;</span>'
X = '<span class="x">&#10005;</span>'


@render_to('milestones.html')
def milestones(request, shared, display_user):
    part135 = part135ifr(display_user)
    return locals()
    
def smallbar(request, val, max_val):
    from small_progress_bar import SmallProgressBar
    return SmallProgressBar(float(val), float(max_val)).as_png()
    
def part135ifr(display_user):
    
    from logbook.models import Flight
    qs = Flight.objects.user(display_user)
    
    ###########################################################################
    
    # only the first 25 hours of simulator instrument
    plane_inst = qs.sim(False).agg('sim_inst') + qs.sim(False).agg('act_inst')
    simulator_inst = qs.sim(True).agg('sim_inst')
    
    if simulator_inst > 25:
        simulator_inst = 25
    
    inst = simulator_inst + plane_inst
    
    ############ part 135 IFR #################################################
    
    part135 = {}
    
    my_numbers = {'total': "%.1f" % qs.sim(False).agg('total'),
                  'night': "%.1f" % qs.sim(False).agg('night'),
                  'p2p': "%.1f" % qs.sim(False).agg('p2p'),
                  'inst': inst}
                  
    goal_numbers = {'total': 1200,
                    'night': 100,
                    'p2p': 500,
                    'inst': 75}
    
    fails = 0
    for item in ('total', 'night', 'p2p', 'inst'):
        mine = my_numbers[item]
        goal = goal_numbers[item]
        
        part135[item] = mine
        part135['goal_%s' % item] = goal

        if float(mine) >= float(goal):
            #the requirement is met
            part135['icon_%s' % item] = V
        else:
            part135['icon_%s' % item] = X
            fails += 1
    
    # if just one requirement is not met, overall good is false,
    # did not meet milestone
    if fails > 0:
        part135['overall'] = X
    else:
        part135['overall'] = V

    return part135

