"""Mathematical boundary verification of a proposed inverse, not VA execution."""
import math
import random
import unittest


def threshold(k,skew,vref):
    return vref*(k/256+skew*(k/256)*(1-k/256))


def proposed_inverse(sample,skew,vref):
    y=min(1.,max(0.,sample/vref))
    u=2*y/(1+skew+math.sqrt((1+skew)**2-4*skew*y))
    estimate=min(255,max(0,math.floor(256*u)))
    if estimate<255 and sample>=threshold(estimate+1,skew,vref):estimate+=1
    if estimate>0 and sample<threshold(estimate,skew,vref):estimate-=1
    return estimate


class InverseBoundaries(unittest.TestCase):
    def test_every_threshold_tie_and_adjacent_representable_value(self):
        checked=0
        for skew in (-.3,-.15,0.,.15,.3):
            for vref in (.8,1.,1.2):
                table=[threshold(k,skew,vref) for k in range(1,256)]
                for boundary in [0.,vref]+table:
                    for sample in (math.nextafter(boundary,-math.inf),boundary,math.nextafter(boundary,math.inf)):
                        expected=sum(sample>=value for value in table)
                        self.assertEqual(proposed_inverse(sample,skew,vref),expected)
                        checked+=1
        self.assertEqual(checked,11565)

    def test_random_full_range_and_saturation(self):
        rng=random.Random(20261008)
        for _ in range(1000):
            skew=rng.uniform(-.3,.3);vref=rng.uniform(.1,2.);sample=rng.uniform(-.3*vref,1.3*vref)
            self.assertEqual(proposed_inverse(sample,skew,vref),sum(sample>=threshold(k,skew,vref) for k in range(1,256)))


if __name__=='__main__':unittest.main()
