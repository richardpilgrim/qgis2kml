from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.core import *
from ogr2kmldialog import ogr2kmlDialog
from ogr2kmlStyle import ogr2kmlClassStyle
from ogr2funz import *
# initialize Qt resources from file resouces.py
import resources_rc
import os
import sys

currentPath = os.path.dirname( __file__ )
sys.path.append( os.path.abspath(currentPath))

import simplekml

class OGR2KML:
    MSG_BOX_TITLE = "ogr2kml Plugin Warning"
    def __init__(self, iface):
        # save reference to the QGIS interface
        self.iface = iface

    def initGui(self):
        # create action that will start plugin configuration
        self.action = QAction(QIcon(":/plugins/ogr2kml/icon.png"), "ogr2kml", self.iface.mainWindow())
        self.action.setWhatsThis("Configuration for ogr2kml plugin")
        #self.action.setStatusTip("This is status tip")
        QObject.connect(self.action, SIGNAL("triggered()"), self.run)

        # add toolbar button and menu item
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu("&ogr2kml", self.action)

        # connect to signal renderComplete which is emitted when canvas rendering is done
        #QObject.connect(self.iface.mapCanvas(), SIGNAL("renderComplete(QPainter *)"), self.renderTest)

    def unload(self):
        # remove the plugin menu item and icon
        self.iface.removePluginMenu("&ogr2kml",self.action)
        self.iface.removeToolBarIcon(self.action)
        
        # disconnect form signal of the canvas
        #QObject.disconnect(self.iface.MapCanvas(), SIGNAL("renderComplete(QPainter *)"), self.renderTest)
        
    def run(self):
        # create and show a configuration dialog or something similar
        self.dlg = ogr2kmlDialog()
        #select directory where save files
        QObject.connect(self.dlg.ui.browseButton, SIGNAL("clicked()"), self.SelectKmlDir)
        #load layer
        layers =  self.iface.activeLayer()
        #OGR layers
        self.layers = {}        
        #Checks for loaded layers, do not load if no layers
        if layers == None:
            QMessageBox.warning(self.iface.mainWindow(), self.MSG_BOX_TITLE, 
            ("No active layer found\n" "Please make one or more OGR layer "\
            "active\n" "Beware of layers sizes for export"), QMessageBox.Ok, 
            QMessageBox.Ok)
            return
        #load qgis mapCanvas
        self.mapCanvas = self.iface.mapCanvas()
        #set number of row in the table
        self.dlg.ui.tablelayers.setColumnCount(3)
        self.dlg.ui.tablelayers.setRowCount(self.mapCanvas.layerCount())
        #add header
        item = QTableWidgetItem('Source')
        self.dlg.ui.tablelayers.setHorizontalHeaderItem(0, item)
        item = QTableWidgetItem('Name field')
        self.dlg.ui.tablelayers.setHorizontalHeaderItem(1, item)
        item = QTableWidgetItem('Desc field')
        self.dlg.ui.tablelayers.setHorizontalHeaderItem(2, item)
        #number of layer
        n_layer = 0
        #Checks vector type and populates the layer list view in opposite 
        #order for the correct visualization on OL
        for i in range(self.mapCanvas.layerCount()-1,-1,-1):
            # define actual layer
            layer = self.mapCanvas.layer(i)
            #check if is a vector (TODO remove when support also other type)
            if layer.type() == layer.VectorLayer and layer.geometryType() == 0:
                nameFields = fieldsName(layer)
                self.layers[layer] = nameFields
                #this is for remove "layerid=*" when use "Unique Value" symbology
                source=layer.source()
                source.remove(QRegExp('\|layerid=[\d]+$'))
                #create and add item of the source to table layer list
                item = QTableWidgetItem(source)
                self.dlg.ui.tablelayers.setItem(n_layer,0, item)
                #
                self.dlg.ui.nameTableItem = QComboBox()
                self.dlg.ui.nameTableItem.addItem('No Name field')
                self.dlg.ui.descTableItem = QComboBox()
                self.dlg.ui.descTableItem.addItem('No Desc field')
                for f in nameFields:
                    self.dlg.ui.nameTableItem.addItem(f)
                    self.dlg.ui.descTableItem.addItem(f)
                self.dlg.ui.tablelayers.setCellWidget(n_layer,1, self.dlg.ui.nameTableItem)
                self.dlg.ui.tablelayers.setCellWidget(n_layer,2, self.dlg.ui.descTableItem)
                n_layer += 1
        self.dlg.ui.tablelayers.resizeColumnsToContents()
        #button for start the plugin
        QObject.connect(self.dlg.ui.buttonBox, SIGNAL("accepted()"), self.WriteKML)
        #button for close the plugin after create openlayers file
        QObject.connect(self.dlg.ui.buttonBox, SIGNAL("rejected()"), self.dlg.close)
        #Set up the default map extent
        Extent = self.mapCanvas.extent()
        if len(self.layers) == 0:
            QMessageBox.warning(self.iface.mainWindow(), self.MSG_BOX_TITLE, 
            ("No active point layer found\n" "Please make one or more OGR layer "\
            "active\n" "Beware of layers sizes for export"), QMessageBox.Ok, 
            QMessageBox.Ok)
            return
        #set the directory where save the files
        global mydir
        mydir=""
        self.dlg.show()

    def SelectKmlDir(self):
        #set up the output dir for new vector files
        global mydir
        mydir = QFileDialog.getExistingDirectory( None,QString("Choose the GML"\
        " files destination folder"),"")
        if not mydir:
            QMessageBox.warning(self.iface.mainWindow(), self.MSG_BOX_TITLE, 
            ("You have to choose a folder"), QMessageBox.Ok, 
            QMessageBox.Ok)
        elif os.access(mydir, os.W_OK):
            self.dlg.ui.kmldirpath.setText(mydir)
            return
        else:
            QMessageBox.warning(self.iface.mainWindow(), self.MSG_BOX_TITLE, 
            ("It is not possible to write into folder '%s'" % mydir), QMessageBox.Ok, 
            QMessageBox.Ok)

    def WriteKML(self):           
        for layer, fields in self.layers.iteritems():
            # create kml for layer
            kml = simplekml.Kml(open=1)
            # create style
            style = ogr2kmlClassStyle(layer)
            provider = layer.dataProvider()
            #set coordinate system of my first vector
            SrsSrc = provider.crs()
            #set wgs84 coordinate system
            SrsDest = QgsCoordinateReferenceSystem(4326)
            #trasform
            SrsTrasform = QgsCoordinateTransform(SrsSrc, SrsDest)
            feat = QgsFeature()
            allAttrs = provider.attributeIndexes()
            provider.select(allAttrs)
            if style.output['type'] != 'singleSymbol':
                idf = idField(layer,style.nameField)
            while provider.nextFeature(feat):
                pnt = kml.newpoint()
                geom = feat.geometry()
                attrs = feat.attributeMap()
                if layer.geometryType() == 0:
                    new_geom = SrsTrasform.transform(geom.asPoint())
                    x = float(new_geom.x())
                    y = float(new_geom.y())
                    pnt.coords = [(x, y)]
                    if style.output['type'] == 'singleSymbol':
                        pnt.style.iconstyle.color = style.output['fillcolor']
                        pnt.style.iconstyle.scale = style.output['size']
                    if style.output['type'] == 'categorizedSymbol':
                        attr = unicode(attrs[idf].toString())
                        pnt.style.iconstyle.color = style.output[attr]['fillcolor']
                        pnt.style.iconstyle.scale = style.output[attr]['size']
                    if style.output['type'] == 'graduatedSymbol':
                        attr = float(unicode(attrs[idf].toString()))
                        for i in range(len(style.ranges)):
                            nl = 'symb%i' % i
                            if attr < style.output[nl]['max'] and attr >= style.output[nl]['min']:
                                pnt.style.iconstyle.color = style.output[nl]['fillcolor']
                                pnt.style.iconstyle.scale = style.output[nl]['size']
                                break
                    pnt.style.iconstyle.icon = None   
                if self.dlg.ui.nameTableItem.currentIndex() != 0:
                    n = attrs[self.dlg.ui.nameTableItem.currentIndex()-1].toString()
                    if n:
                        pnt.name = n 
                if self.dlg.ui.descTableItem.currentIndex() != 0:
                    d = attrs[self.dlg.ui.descTableItem.currentIndex()-1].toString()
                    if d:
                        pnt.description = d
            
            if self.dlg.ui.outputFormCombo.currentIndex() == 0:
                kml.save(os.path.join(str(self.dlg.ui.kmldirpath.text()),
                        '%s.kml' % layer.name()))
            elif self.dlg.ui.outputFormCombo.currentIndex() == 1:
                kml.savekmz(os.path.join(str(self.dlg.ui.kmldirpath.text()),
                        '%s.kmz' % layer.name()))
            