# encoding: utf-8

import os

from django.contrib.gis.db import models
#from django.contrib.gis.utils import LayerMapping
from django.contrib.auth.models import User
from django.db.models import Count
from django.http import Http404

from constants import LOCATION_TYPE, LOCATION_CLASS

from main.enhanced_model import GeoQuerySetManager, EnhancedModel
from queryset_manager import * 

class WikiMixins(object):
    def region_category(self):
        return "{0} ({1}) Airports".format(self.region.name, self.country.code).encode('utf-8')
    
    def country_category(self):
        return "{0} Airports".format(self.country.name)
    
    def any_ident(self):
        return  self.local_identifier or\
                self.icao_identifier or\
                self.iata_identifier
    
    def wiki_coord(self):
        return u"{0}° {1}°".format(self.location.y, self.location.x).encode('utf-8')
    
    def historical(self):
        out = []
        for hist in self.historicalident_set.all().iterator():
            out.append("{{Historical|%s|%s|%s}}" % (hist.identifier,
                                                    hist.start,
                                                    hist.end))
            
        return "\n".join(out)

class Location(EnhancedModel, WikiMixins):
    
    objects = GeoQuerySetManager(LocationQuerySet)
    
    ## -----------------------------------------------------------------------
    
    #navaid, airport, custom, etc
    loc_class = models.IntegerField(choices=LOCATION_CLASS,
                                         default=0, blank=True, null=True)
                                         
    user = models.ForeignKey(User, null=True)
    
    identifier = models.CharField(max_length=8, db_index=True)
    icao_identifier = models.CharField(max_length=4, blank=True)
    iata_identifier = models.CharField(max_length=3, blank=True)
    local_identifier = models.CharField(max_length=8, blank=True)
    
    country = models.ForeignKey("Country", null=True, blank=True)
    region = models.ForeignKey("Region", null=True, blank=True)
    
    # vor, dme, small airport, etc
    loc_type = models.IntegerField(choices=LOCATION_TYPE, default=0)

    name = models.CharField(max_length=96, blank=True)
    municipality = models.CharField(max_length=60, blank=True)
    elevation = models.IntegerField(null=True, blank=True)
    
    location = models.PointField(null=True, blank=True)
    
    ## -----------------------------------------------------------------------
    
    def __unicode__(self):
        return u"%s" % self.identifier
    
    @classmethod
    def get_profiles(self, val, field):
        """
        Returns the profiles of the users who have flown in this
        type/tail/whatever
        """
                   
        from profile.models import Profile
        kwarg = {"user__flight__route__routebase__location__%s__iexact" % field: val}
        
        return Profile.objects\
                      .filter(social=True)\
                      .filter(**kwarg)\
                      .values('user__username', 'user__id', 'logbook_share')\
                      .order_by('user__username')\
                      .distinct()
    
    @classmethod
    def goof(cls, *args, **kwargs):
        """
        An improved "get_object_or_404" method that deals with there potentially
        being multiple airports with the same identifier.
        """
        
        try:
            loc = cls.objects.filter(*args, **kwargs)[0]
        except IndexError:
            raise Http404('no such airport')
        
        return loc
    
    
    def kml_icon(self):
        """
        Returns the proper KML icon class based on the loc_type attribute
        for use in the KML files
        """
        
        from collections import defaultdict
        from itertools import repeat

        # a function that always returns a constant
        l = lambda value: repeat(value).next

        icons = defaultdict(l('#white'), {
                    0: "#white",     #unknown
                    1: "#yellow",    #small
                    2: "#orange",    #medium
                    3: "#red",       #large
                    4: "#gray",      #closed
                    5: "#purple",    #heliport
                    6: "#cyan",      #seaport
                    7: "#teal",      #baloon port
                    8: "#green",     #off airport
                })
                        
        return icons[self.loc_type]
    
       
    def region_name(self):
        if self.region:
            return self.region.name
        return "(unassigned)" # will be filtered away with other methods
        
    def country_name(self):
        if self.country:
            return self.country.name
        return "(unassigned)"

    def display_name(self):
        """Forward facing __unicode__, used in KML and similiar"""
        return "%s - %s" % (self.identifier, self.name)
        
    def line_display(self):
        "What gets put on the line on the route column"
        return self.identifier
        
    def title_display(self):
        "What gets put in the tooltip on the route column"
        return self.location_summary()
    
    def location_summary(self):
        """A friendly named location
           EX: 'Newark, Ohio', 'Lilongwe, Malawi'.
        """
          
        items = []
        for item in (self.municipality, self.region_name(), self.country_name(), ):
            if item and item != "United States" and item != "(unassigned)":
                items.append(item)

        text = ", ".join(items)
        
        if self.loc_class == 2:
            ## if it's a navaid, add the name of the navaid as well as the
            ## navaid type
            return "%s %s, %s" % (self.name, self.get_loc_type_display(), text)
        
        if text == '':
            return "Custom identifier (coordinates unknown)"
        
        return text
    
    def get_users(self):
        """ Returns all users who have flown to this location """
        
        from django.contrib.auth.models import User      
        return User.objects\
                   .filter(profile__social=True)\
                   .filter(flight__route__routebase__location__id=self.id)\
                   .distinct()\
    
    def save(self, *args, **kwargs):
        """ if it's a custom, automatically look up to see which country and
        or state the custom location falls into"""
        
        skip_find_region = False
        if 'skip_find_region' in kwargs.keys():
            skip_find_region = kwargs.pop('skip_find_region')
        
        ## just save if it's an airport
        if self.loc_class == 1:
            return super(Location, self).save(*args, **kwargs)
        
        if self.location and not skip_find_region:
            # automatically find which country the coordinates fall into
            loc = self.location.wkt
            
            country = getattr(
              WorldBorders.goon(mpoly__contains=loc), 'iso2',''
            )
                
            self.country = Country(code=country) # code = pk
            
            if country=='US':
                state = None
                # in the US, now find the state
                state = getattr(
                  USStates.goon(mpoly__contains=loc), 'state',''
                )
                
                if not state:
                    print "NO STATE: %s" % self.identifier
                    
                if state:   
                    region = state.upper()
                else:
                    region = "U-A"
                    
                self.region = Region.goon(code="US-%s" % region)
                
        return super(Location, self).save(*args, **kwargs)
    
###############################################################################

class HistoricalIdent(EnhancedModel):
    start = models.DateField(default='1900-01-01')
    end = models.DateField()
    
    identifier = models.CharField(max_length=8)
    
    current_location = models.ForeignKey(Location)
    
    def __unicode__(self):
        s = "{old} -> {new} -- {begin} - {end}"
        return s.format(old=self.identifier,
                        new=self.current_location,
                        begin=self.start,
                        end=self.end)
    
    def curr_name(self):
        return "{0} - {1}".format(self.current_location.name,
                                  self.current_location.location_summary())

###############################################################################
  
class Region(EnhancedModel):
    
    ## add custom filterset manager
    objects = GeoQuerySetManager(CountryRegionQuerySet)
    
    code = models.CharField(max_length=48)
    country = models.CharField(max_length=2)
    name = models.CharField(max_length=60)
    
    def __unicode__(self):
        return self.name
    
    class Meta:
        ordering = ('name', )
    
    def country_name(self):
        return Country.objects.get(code=self.country)

##############################################################################

class Country(models.Model):

    objects = GeoQuerySetManager(CountryRegionQuerySet)
    
    name = models.CharField(max_length=48)
    code = models.CharField(max_length=2, primary_key=True)
    continent = models.CharField(max_length=2)
    
    def __unicode__(self):
        return self.name
    
    class Meta:
        verbose_name_plural = "Countries"
        ordering = ('name', )
    
##############################################################################    
    
    
class WorldBorders(EnhancedModel):
    name = models.CharField(max_length=50)
    area = models.IntegerField()
    pop2005 = models.IntegerField('Population 2005')
    fips = models.CharField('FIPS Code', max_length=2)
    iso2 = models.CharField('2 Digit ISO', max_length=2)
    iso3 = models.CharField('3 Digit ISO', max_length=3)
    un = models.IntegerField('United Nations Code')
    region = models.IntegerField('Region Code')
    subregion = models.IntegerField('Sub-Region Code')
    lon = models.FloatField()
    lat = models.FloatField()

    mpoly = models.MultiPolygonField()
    objects = models.GeoManager()

    class Meta:
        verbose_name_plural = "World Borders"
        ordering = ('name', )

    def __unicode__(self):
        return self.name

worldborders_mapping = {
    'fips' : 'FIPS',
    'iso2' : 'ISO2',
    'iso3' : 'ISO3',
    'un' : 'UN',
    'name' : 'NAME',
    'area' : 'AREA',
    'pop2005' : 'POP2005',
    'region' : 'REGION',
    'subregion' : 'SUBREGION',
    'lon' : 'LON',
    'lat' : 'LAT',
    'mpoly' : 'MULTIPOLYGON',
}

def import_world(verbose=True):
    
    world_shp = os.path.abspath(
                                os.path.join(os.path.dirname(__file__),
                                'data/world/TM_WORLD_BORDERS-0.3.shp')
                            )
                            
    lm = LayerMapping(WorldBorders, world_shp, worldborders_mapping,
                      transform=False, encoding='iso-8859-1')

    lm.save(strict=True, verbose=verbose)

##############################################################################

class USStates(models.Model):
    state = models.CharField(max_length=5)
    name = models.CharField(max_length=24)
    lon = models.FloatField()
    lat = models.FloatField()
    mpoly = models.MultiPolygonField(srid=4269)
    objects = models.GeoManager()
    
    class Meta:
        verbose_name_plural = "US State Borders"
        ordering = ('name', )
    
    def __unicode__(self):
        return self.name
    
    @classmethod
    def goon(cls, *args, **kwargs):
        from annoying.functions import get_object_or_None
        return get_object_or_None(cls,  *args, **kwargs)

usstates_mapping = {
    'state' : 'STATE',
    'name' : 'NAME',
    'lon' : 'LON',
    'lat' : 'LAT',
    'mpoly' : 'MULTIPOLYGON',
}

def import_state(verbose=True):
    us_shp = os.path.abspath(
                                os.path.join(os.path.dirname(__file__),
                                'data/states/s_01au07.shp')
                            )
                            
    lm = LayerMapping(USStates, us_shp, usstates_mapping,
                      transform=False, encoding='iso-8859-1')

    lm.save(strict=True, verbose=verbose)
