import os
import zipfile
from urllib import urlencode
from urllib2 import urlopen
import json
import collections

from django import forms
from django.contrib import gis
from django.db import models
from django.contrib.auth.models import User
from django.core import validators
from django.contrib.gis.db import models

# requires GeoDjango Libraries
#############
from django.contrib.gis.gdal import DataSource

# the basepath for file uploads (needed to read shapefiles)
from settings import MEDIA_ROOT

def get_upload_path(instance, filename):
    return instance.get_upload_path(filename)

class Authored(models.Model):
    """For things made by people """
    author = models.ForeignKey(User)
    class Meta:
        abstract=True

class Named(models.Model):
    """just putting names on models"""
    name = models.CharField(max_length=200, null=True, blank=True)
    class Meta:
        abstract=True

class Dated(models.Model):
    date_added = models.DateTimeField(auto_now_add=True)
    date_edited = models.DateTimeField(auto_now=True)
    class Meta:
        abstract=True

class Noted(models.Model):
    notes = models.TextField(null=True, blank=True)
    class Meta:
        abstract=True

class GeomType(models.Model):
    """adding geomtery type"""
    geometry_type = models.CharField(max_length=200, null=True, blank=True)
    class Meta:
        abstract=True

class GeomFields(models.Model):
    """adding attribute fields"""
    fields = models.TextField()
    class Meta:
        abstract=True
   
class Units(models.Model):
    """adding attribute fields"""
    units = models.TextField()
    class Meta:
        abstract=True
        
class FilePath(models.Model):
    """adding attribute fields"""
    file_location = models.TextField()
    class Meta:
        abstract=True

class OGRGeom(models.Model):
    """adding attribute fields"""
    ogr_geom = models.GeometryField()
    objects = models.GeoManager()
    class Meta:
        abstract=True

class DataFile(Dated):
    """Data files represent individual file uploads.
    They are used to construct DataLayers.
    """
    file = models.FileField(upload_to=get_upload_path)
    upload = models.ForeignKey('UploadEvent', null=True, blank=True)
    
    def get_upload_path(self, filename):
        return 'uploads/%s/%s' % (self.upload.user.username, filename)
    
    def abs_path(self):
        """returns the full path of the zip file"""
        return os.path.join( MEDIA_ROOT, self.file.__unicode__())
    
    def extract_path(self):
        """returns a directory path for extracting zip files to"""
        return os.path.splitext( self.abs_path() )[0]
    #
    #
    def path_of_part(self, ext):
        """give an file extension of a specific file within the zip file, and
        get an absolute path to the extracted file with that extension.
        Assumes that the contents have been extracted.
        Returns `None` if the file can't be found
        """
        path_to_part = None
        all_paths = os.walk(self.extract_path())
        for tree in all_paths:
            if len(tree[2]) > 0:
                for file_name in tree[2]:
                    if file_name.endswith(ext) and not file_name.startswith('.'):
                        path_to_part = tree[0]
                        break
                
        return path_to_part
            
    def __unicode__(self):
        return "DataFile: %s" % self.file.url
    
    def get_layer_data(self):
        """extracts relevant data for building LayerData objects
        meant to be used as initial data for LayerReview Forms
        """
        data = {}
        data['id'] = self.id
        abs_path = self.abs_path()
        # see if we need to extract it
        extract_dir = self.extract_path()
        basename = os.path.split( extract_dir )[1]
        #print basename
        if not os.path.isdir( extract_dir ):
            # extract it to a directory with that name
            os.mkdir( extract_dir )
            zip_file = zipfile.ZipFile( self.file )
            zip_file.extractall( extract_dir )

        # get shape type
        shape_path = self.path_of_part('.shp')
        ds = DataSource( shape_path )
        layer = ds[0]
        'Here we add a check for geometry types???'
        
        data['geometry_type'] = layer.geom_type.name
        data['name'] = layer.name
        data['file_location'] = shape_path
        data['srs'] = None
        data['units'] = 'Unknown'
        
        #for l in layer:
        #    print l.geom.tuple
        if layer.srs:
            srs = layer.srs
            try:
                # use the gdal to extract srs
                srs.identify_epsg()
                data['srs'] = srs['AUTHORITY', 1]
                data['units'] = srs.units[1]
            except:
                pass
        if not data['srs']:
            # use prj2epsg API to extract srs
            data['srs'] = self.get_srs(data)
        if not data['srs']:
            data['srs'] = 'No known Spatial Reference System'

        return data

    def get_srs(self, data):
        """takes the prj data and sends it to the prj2epsg API.
        The API returns the srs code if found.
        """
        api_srs = {}
        prj_path = self.path_of_part('.prj')
        try:
            prj_path = prj_path+"/"+str(data['name'])
            if prj_path:
                prj_text = open(prj_path+'.prj', 'r').read()
                query = urlencode({
                    'exact' : False,
                    'error' : True,
                    'terms' : prj_text})
                webres = urlopen('http://prj2epsg.org/search.json', query)
                jres = json.loads(webres.read())
                if jres['codes']:
                    api_srs['message'] = 'An exact match was found'
                    api_srs['srs'] = int(jres['codes'][0]['code'])
                    data['srs'] = jres['codes'][0]['code']
                else:
                    data['srs'] = None
                return data['srs']
            else:
                pass
        except: return None
    
class UploadEvent(models.Model):
    '''Will save the upload event everytime a user uploads a file'''
    '''saved in upload() in views.py'''
    user = models.ForeignKey(User)
    date = models.DateTimeField(auto_now_add=True)
    def __unicode__(self):
        return "UploadEvent: %s" % self.date


class StartSign2(Named, Authored, Dated):
    '''saved in the tasks.py'''
    '''indicates the starting of making the graph before computation'''
    upload = models.ForeignKey(UploadEvent)

class BloockNUM2(Named, Authored, Dated):
    '''save the block number of current project'''
    number = models.IntegerField(null=True, blank=True)
    start = models.ForeignKey(StartSign2)


class DataSave5(Named, Authored, Dated):
    '''save the data that is unput by the user (name, location, description, project id)'''
    prjname = models.TextField(null=True, blank=True)
    location = models.TextField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    start = models.ForeignKey(StartSign2)
    d_id = models.IntegerField(null=True, blank=True)

class SaveJSON3(Named, Authored, Dated):
    '''template'''
    topo_json = models.TextField(null=True, blank=True)
    block_index = models.IntegerField(null=True, blank=True)
    srs = models.TextField(null=True, blank=True)
    
    class Meta:
        abstract=True

class FinishSign3(Named, Authored, Dated):
    '''saves the finish state of the computation'''
    start = models.ForeignKey(StartSign2)

class StepStart2(Named, Authored, Dated):
    '''saves the start sate of the computation and the finish state of making the graph'''
    start = models.ForeignKey(StartSign2)


class RoadJSON6(SaveJSON3):
    '''saves the road json'''
    start = models.ForeignKey(StartSign2)
    number = models.ForeignKey(BloockNUM2)
    def __unicode__(self):
        return "RoadJSON: %s, Created by:%s " % (str(self.name), (str(self.author)))

class InteriorJSON6(SaveJSON3):
    '''saves the interior parcels json'''
    start = models.ForeignKey(StartSign2)
    number = models.ForeignKey(BloockNUM2)
    def __unicode__(self):
        return "InteriorJSON: %s, Created by:%s " % (str(self.name), (str(self.author)))

class DefineBarriers2(SaveJSON3):
    '''saves the barrier index and saves the original json'''
    barrier_index = models.TextField(null=True, blank=True)
    start = models.ForeignKey(StartSign2)
    number = models.ForeignKey(BloockNUM2)
    def __unicode__(self):
        return "BlockJSON: %s, Created by:%s " % (str(self.name), (str(self.author)))
    
    
class IntermediateJSON7(Named, Authored, Dated):
    '''saves the intermediate steps'''
    '''step_index is the index of the step for the current block'''
    '''block_index is the index of the current block for the current project'''
    step_index = models.IntegerField(null=True, blank=True)
    topo_json = models.TextField(null=True, blank=True)
    road_json = models.TextField(null=True, blank=True)
    block_index = models.IntegerField(null=True, blank=True)
    srs = models.TextField(null=True, blank=True)
    start = models.ForeignKey(StartSign2)
    number = models.ForeignKey(BloockNUM2)
    def __unicode__(self):
        return "IntermediateJSON: %s, Created by:%s " % (str(self.name), (str(self.author)))


class DataLayer(Named, Authored, Dated, Noted, GeomType,FilePath, Units):
    srs = models.CharField(max_length=50, null=True, blank=True)
    files = models.ManyToManyField('DataFile', null=True, blank=True )
    tags = models.CharField(max_length=50, null=True, blank=True)
    objects = models.GeoManager()
    def get_browsing_data(self):
        obj = vars(self)
        tags = self.tag_set.all()
        return obj
    def __unicode__(self):
        return "DataLayer: %s" % self.name


class Attribute(Named):
    layer = models.ForeignKey(DataLayer)
    data_type = models.CharField(max_length=100)
    def __unicode__(self):
        return "Attribute: %s" % self.name

class SiteConfiguration(Named, Authored, Dated, Noted):
    """A model for storing the different site configurations that someone has
    made. It must have a site_layer that defines the separate sites.
        It can add other layers (these should maybe be ordered with
        django-sortedm2m )
        It has a radius and srs code.
        the srs attribute is defined so that it could be proj or WKT text or an
        EPSG code. It will be used to define the coordinate system for the
        built sites.
        This should maybe be immutable. If something is changed, it should make
        a new instance, so that we always can track down the settings used for
        a particular SiteSet.
    """
    site_layer = models.ForeignKey('DataLayer',
            related_name='siteconfiguration_site')
    other_layers = models.ManyToManyField('DataLayer',
            related_name='siteconfiguration_other',
            null=True, blank=True)
    radius = models.IntegerField( default=1000 )
    srs = models.CharField( max_length=500, null=True, blank=True)
    objects = models.GeoManager()
    
    def __unicode__(self):
        return "SiteConfiguration: %s" % self.name
 
def create_from_shapefile(self, path):
    ds = DataSource(path)
    layer = ds[0]
    for feature in layer:
        DataLayer.objects.create(geometry=feature['geometry'], field=feature['field'])
        
class UserProfile(models.Model):
    '''defines User as an one to one relationship model'''
    user = models.OneToOneField(User)
    activation_key = models.CharField(max_length=30)
