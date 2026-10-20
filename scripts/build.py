# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Leon Zandman

import FreeCAD as App
import FreeCADGui as Gui
import Part, Sketcher, MeshPart, Draft, math, os
import importSVG, tempfile, xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGES = os.path.join(ROOT, 'images')
EXPORTS = os.path.join(ROOT, 'exports')
os.makedirs(IMAGES, exist_ok=True)
os.makedirs(EXPORTS, exist_ok=True)
doc = App.newDocument('USB_Behuizing')
doc.License = 'CC BY 4.0'
doc.LicenseURL = 'https://creativecommons.org/licenses/by/4.0/'
doc.Comment = 'Eigen behuizingsontwerp: CC BY 4.0. RDW-logo en ander materiaal van derden uitgezonderd; zie LICENSE.md.'
p = doc.addObject('Spreadsheet::Sheet', 'Parameters')
rows = [
    ('Wall', 1.8, 'Wanddikte'),
    ('Clearance', 0.3, 'Speling per zijde'),
    ('FrontClearance', 0.2, 'Speling voorzijde print'),
    ('BoardLength', 29.8, 'Printlengte inclusief voorste lippen'),
    ('BoardWidth', 14.2, 'Maximale printbreedte'),
    ('ConnectorLength', 15.0, 'Connectorlengte'),
    ('ConnectorWidth', 12.1, 'Connectorbreedte'),
    ('ConnectorHeight', 4.6, 'Connectorhoogte'),
    ('Height', 9.6, 'Buitenhoogte; binnenruimte 6 mm plus twee wanden'),
]
for i, (alias, value, label) in enumerate(rows, 1):
    p.set('A'+str(i), label)
    p.set('B'+str(i), str(value)+' mm')
    p.setAlias('B'+str(i), alias)
p.set('B9', '=6 mm + 2*B1')
for i, (alias, formula, label) in enumerate([
    ('Front', '=B6-B3-B1', 'Begin behuizing vanaf connectortip'),
    ('Rear', '=B6+B4+B2+B1', 'Achtervlak vanaf connectortip'),
    ('Width', '=B5+2*B2+2*B1', 'Buitenbreedte'),
    ('Length', '=B11-B10', 'Buitenlengte'),
    ('SeamHeight', '=B8/2+B2', 'Deelnaad boven hartlijn connector'),
    ('LowerHeight', '=B9/2+B14', 'Hoogte onderbak'),
    ('UpperHeight', '=B9/2-B14', 'Hoogte deksel'),
    ('RetentionOverlap', '=(B5-B7-2*B2)/2', 'Print-overlap achter voorwand per zijde'),
    ('CornerChamfer', '1 mm', 'Facetmaat verticale buitenhoeken'),
    ('TextHeight', '0.8 mm', 'Verhoogde tekst'),
    ('TextSize', '6 mm', 'Letterhoogte Leon'),
    ('LogoWidth', '28 mm', 'Breedte RDW-logo'),
    ('LogoHeight', '0.8 mm', 'Verhoogd RDW-logo'),
    ('FrontNotchFromRear', '28 mm', 'Achterrand tot hart voorste uitsparing (interpretatie tekening)'),
    ('FrontNotchWidth', '2.5 mm', 'Breedte voorste uitsparingen'),
    ('FrontNotchDepth', '2 mm', 'Diepte voorste uitsparingen'),
    ('RearNotchDepth', '3 mm', 'Diepte achterste inkeping'),
    ('RearNotchWidth', '8.4 mm', 'Breedte achterste inkeping'),
    ('LockRadius', '=B24/2-B2', 'Straal voorste nokken na speling'),
    ('FrontNotchX', '=B6+B4-B23', 'Hart voorste nokken vanaf connectortip'),
    ('FrontNotchY', '=B5/2-B25+B24/2', 'Hart voorste nokken uit midden'),
    ('EyeExtension', '9 mm', 'Uitsteek sleutelhangoog achter behuizing'),
    ('EyeWidth', '10 mm', 'Breedte sleutelhangoog'),
    ('EyeThickness', '4 mm', 'Dikte sleutelhangoog'),
    ('EyeHole', '4.5 mm', 'Vrije breedte ringopening tussen vlakke zijden'),
], 10):
    p.set('A'+str(i), label)
    p.set('B'+str(i), formula)
    p.setAlias('B'+str(i), alias)
p.setColumnWidth('A', 390)
p.setColumnWidth('B', 130)
doc.recompute()

def rectangle(body, name, xmin, ymin, length, width, exprs, zexpr):
    s = doc.addObject('Sketcher::SketchObject', name)
    body.addObject(s)
    pts = [(xmin,ymin),(xmin+length,ymin),(xmin+length,ymin+width),(xmin,ymin+width)]
    for i in range(4):
        a,b = pts[i], pts[(i+1)%4]
        s.addGeometry(Part.LineSegment(App.Vector(*a,0),App.Vector(*b,0)),False)
    for i in range(4):
        s.addConstraint(Sketcher.Constraint('Coincident',i,2,(i+1)%4,1))
        s.addConstraint(Sketcher.Constraint('Horizontal' if i%2==0 else 'Vertical',i))
    for c,expression in zip([
        Sketcher.Constraint('DistanceX',0,1,xmin),
        Sketcher.Constraint('DistanceY',0,1,ymin),
        Sketcher.Constraint('Distance',0,length),
        Sketcher.Constraint('Distance',1,width),
    ],exprs):
        n = s.addConstraint(c)
        s.setExpression('Constraints['+str(n)+']',expression)
    s.setExpression('Placement.Base.z',zexpr)
    return s

def shell(name, upper=False):
    b = doc.addObject('PartDesign::Body',name)
    b.Label = 'Bovenhelft' if upper else 'Onderhelft'
    s=rectangle(b,name+'_Outline',13.0,-9.2,33.9,18.4,
        ['Parameters.Front','-Parameters.Width / 2','Parameters.Length','Parameters.Width'],
        '-Parameters.Height / 2')
    pad=b.newObject('PartDesign::Pad',name+'_Pad')
    pad.Profile=s
    pad.setExpression('Length','Parameters.UpperHeight' if upper else 'Parameters.LowerHeight')
    doc.recompute()
    s.Visibility=False
    cavity=rectangle(b,name+'_Cavity',14.8,-7.4,30.3,14.8,
        ['Parameters.ConnectorLength - Parameters.FrontClearance',
         '-Parameters.BoardWidth / 2 - Parameters.Clearance',
         'Parameters.BoardLength + Parameters.FrontClearance + Parameters.Clearance',
         'Parameters.BoardWidth + 2 * Parameters.Clearance'],
         '-Parameters.SeamHeight' if upper else 'Parameters.SeamHeight')
    pocket=b.newObject('PartDesign::Pocket',name+'_Pocket')
    pocket.Profile=cavity
    pocket.setExpression('Length',
        'Parameters.UpperHeight - Parameters.Wall' if upper else
        'Parameters.LowerHeight - Parameters.Wall')
    doc.recompute()
    pad.Visibility=False
    cavity.Visibility=False
    if upper:
        pocket.ViewObject.ShapeColor=(0.03,0.16,0.85)
        pocket.ViewObject.LineColor=(0.02,0.05,0.18)
        b.ViewObject.ShapeColor=(0.03,0.16,0.85)
        b.Placement=App.Placement(App.Vector(),App.Rotation(App.Vector(1,0,0),180))
        return b
    opening=rectangle(b,name+'_Opening',12.0,-6.35,3.8,12.7,
        ['Parameters.Front - 1 mm',
         '-Parameters.ConnectorWidth / 2 - Parameters.Clearance',
         'Parameters.Wall + 2 mm',
         'Parameters.ConnectorWidth + 2 * Parameters.Clearance'],'Parameters.SeamHeight')
    cut=b.newObject('PartDesign::Pocket',name+'_ConnectorPocket')
    cut.Profile=opening
    cut.setExpression('Length','Parameters.ConnectorHeight + 2 * Parameters.Clearance')
    doc.recompute()
    pocket.Visibility=False
    opening.Visibility=False
    cut.ViewObject.ShapeColor=(0.03,0.16,0.85)
    b.ViewObject.ShapeColor=(0.03,0.16,0.85)
    cut.ViewObject.LineColor=(0.02,0.05,0.18)
    return b

lower=shell('Lower')
upper=shell('Upper',True)
doc.recompute()

# Hardware is a dimensional reference; add_board_locks later cuts its notches.
ref=doc.addObject('App::DocumentObjectGroup','HardwareReference')
ref.Label='Hardware referentie (componentposities bij benadering)'
pcb=doc.addObject('PartDesign::Feature','PCB_Reference')
pcb.Label='Printplaat 29,8 x 14,2; dikte aangenomen 1 mm'
pcb.Shape=Part.makeBox(29.8,14.2,1,App.Vector(15,-7.1,-0.5))
pcb.ViewObject.ShapeColor=(0.03,0.35,0.12)
ref.addObject(pcb)
connector=doc.addObject('PartDesign::Feature','USB_A_Reference')
connector.Label='USB-A connector 15 x 12,1 x 4,6 mm'
metal=Part.makeBox(15,12.1,4.6,App.Vector(0,-6.05,-2.3))
metal=metal.cut(Part.makeBox(13.5,11.3,3.8,App.Vector(-0.1,-5.65,-1.9)))
for yy in (-3.1,1.1):
    metal=metal.cut(Part.makeBox(2,2,0.8,App.Vector(4,yy,1.8)))
connector.Shape=metal
connector.ViewObject.ShapeColor=(0.75,0.77,0.8)
ref.addObject(connector)
tongue=doc.addObject('PartDesign::Feature','USB_Insulator')
tongue.Shape=Part.makeBox(11,10.4,1.2,App.Vector(1,-5.2,-1.8))
tongue.ViewObject.ShapeColor=(0.07,0.07,0.07)
ref.addObject(tongue)
pcb.Visibility=True
doc.recompute()

def finish_model(doc):
    p=doc.Parameters
    for body in (doc.Lower,doc.Upper):
        base=body.Tip
        bounds=base.Shape.BoundBox
        edges=[]
        for i,edge in enumerate(base.Shape.Edges,1):
            if len(edge.Vertexes)!=2:
                continue
            a,b=[v.Point for v in edge.Vertexes]
            if (abs(a.x-b.x)<1e-7 and abs(a.y-b.y)<1e-7
                and abs(a.z-b.z)>1e-7
                and min(abs(a.x-bounds.XMin),abs(a.x-bounds.XMax))<1e-7
                and min(abs(a.y-bounds.YMin),abs(a.y-bounds.YMax))<1e-7):
                edges.append('Edge'+str(i))
        assert len(edges)==4
        chamfer=body.newObject('PartDesign::Chamfer',body.Name+'_Facets')
        chamfer.Base=(base,edges)
        chamfer.setExpression('Size','Parameters.CornerChamfer')
        doc.recompute()
        assert chamfer.Shape.isValid() and len(chamfer.Shape.Solids)==1
        base.Visibility=False
        chamfer.ViewObject.ShapeColor=(0.03,0.16,0.85)
        chamfer.ViewObject.LineColor=(0.02,0.05,0.18)

    fonts=[
        '/System/Library/Fonts/HelveticaNeue.ttc',
        '/Library/Fonts/HelveticaNeue.ttf',
    ]
    font=next((f for f in fonts if os.path.isfile(f)),None)
    if font is None:
        raise RuntimeError('Helvetica Neue is required to build Leon text; set its font path in fonts.')
    lettering=Draft.make_shapestring(String='Leon',FontFile=font,Size=float(p.TextSize),Tracking=0)
    lettering.Label='Leon - letterbron'
    construction=doc.addObject('App::DocumentObjectGroup','Construction')
    construction.Label='Constructie - tekstbron'
    construction.addObject(lettering)
    doc.recompute()
    text=Draft.make_sketch(lettering,autoconstraints=False)
    text.Label='Leon - tekstprofiel'
    doc.Upper.addObject(text)
    # Rotate the local lettering plane so it reads correctly after the lid's
    # existing 180-degree body rotation and extrudes outwards from the roof.
    bounds=lettering.Shape.BoundBox
    cx,cy=bounds.Center.x,bounds.Center.y
    text.Placement=App.Placement(
        App.Vector((float(p.Front)+float(p.Rear))/2-cx,cy,-float(p.Height)/2),
        App.Rotation(App.Vector(1,0,0),180))
    text.setExpression('Placement.Base.z','-Parameters.Height / 2')
    text.setExpression('Placement.Base.x','(Parameters.Front + Parameters.Rear) / 2 - '+str(cx)+' mm')
    for i in range(text.GeometryCount):
        text.addConstraint(Sketcher.Constraint('Block',i))
    doc.recompute()
    assert abs(text.Shape.BoundBox.Center.x-(float(p.Front)+float(p.Rear))/2)<1e-6
    assert abs(text.Shape.BoundBox.Center.y)<1e-6
    relief=doc.Upper.newObject('PartDesign::Pad','Leon_Relief')
    relief.Label='Leon - verhoogde tekst'
    relief.Profile=text
    relief.setExpression('Length','Parameters.TextHeight')
    doc.recompute()
    assert relief.Shape.isValid() and len(relief.Shape.Solids)==1
    assert abs(doc.Upper.Shape.BoundBox.XLength-float(p.Length))<1e-6
    assert abs(doc.Upper.Shape.BoundBox.YLength-float(p.Width))<1e-6
    lettering.Visibility=False
    text.Visibility=False
    doc.Upper_Facets.Visibility=False
    relief.ViewObject.ShapeColor=(0.03,0.16,0.85)
    relief.ViewObject.LineColor=(0.02,0.05,0.18)

finish_model(doc)

def add_rdw_logo(doc, imported=None):
    p=doc.Parameters
    if imported is None:
        # Import only visible artwork. Illustrator masks describe clipping
        # bounds and must not become raised rectangles in the CAD model.
        svg=ET.parse(os.path.join(ROOT,'references','Logo Particulier Zakelijk en NRD.svg'))
        for parent in svg.iter():
            for child in list(parent):
                if child.tag.split('}')[-1] in ('defs','mask','filter','style'):
                    parent.remove(child)
            if parent.tag.split('}')[-1] in ('path','polygon'):
                parent.attrib.pop('class',None)
                parent.set('fill','#000000')
                parent.set('fill-rule','evenodd')
        # Absolute units also avoid FreeCAD's interactive DPI prompt.
        svg.getroot().set('width','188mm')
        svg.getroot().set('height','62.7mm')
        ET.register_namespace('','http://www.w3.org/2000/svg')
        ET.register_namespace('xlink','http://www.w3.org/1999/xlink')
        before={o.Name for o in doc.Objects}
        with tempfile.TemporaryDirectory() as temporary:
            filename=os.path.join(temporary,'rdw.svg')
            svg.write(filename,encoding='utf-8',xml_declaration=True)
            importSVG.insert(filename,doc.Name)
        imported=[o for o in doc.Objects if o.Name not in before]
    assert len(imported)==4
    logo_group=doc.addObject('App::DocumentObjectGroup','RDW_Source')
    logo_group.Label='RDW - SVG-bron'
    doc.Construction.addObject(logo_group)
    for obj in imported:
        logo_group.addObject(obj)
        obj.Visibility=False
        assert len(obj.Shape.Faces)==1 and obj.Shape.isValid()
    shape=Part.makeCompound([o.Shape for o in imported])
    shape.scale(float(p.LogoWidth)/shape.BoundBox.XLength)
    profile_source=doc.addObject('PartDesign::Feature','RDW_Scaled')
    profile_source.Label='RDW - geschaald profiel'
    profile_source.Shape=shape
    logo_group.addObject(profile_source)
    doc.recompute()
    sketch=Draft.make_sketch(profile_source,autoconstraints=False)
    sketch.Label='RDW - logoprofiel'
    doc.Lower.addObject(sketch)
    cx,cy=shape.BoundBox.Center.x,shape.BoundBox.Center.y
    sketch.Placement=App.Placement(
        App.Vector((float(p.Front)+float(p.Rear))/2-cx,cy,-float(p.Height)/2),
        App.Rotation(App.Vector(1,0,0),180))
    sketch.setExpression('Placement.Base.x','(Parameters.Front + Parameters.Rear) / 2 - '+str(cx)+' mm')
    sketch.setExpression('Placement.Base.z','-Parameters.Height / 2')
    for i in range(sketch.GeometryCount):
        sketch.addConstraint(Sketcher.Constraint('Block',i))
    doc.recompute()
    base=doc.Lower_Facets
    relief=doc.Lower.newObject('PartDesign::Pad','RDW_Relief')
    relief.Label='RDW - verhoogd logo'
    relief.Profile=sketch
    relief.setExpression('Length','Parameters.LogoHeight')
    doc.recompute()
    assert relief.Shape.isValid() and len(relief.Shape.Solids)==1
    assert sketch.FullyConstrained
    assert abs(sketch.Shape.BoundBox.Center.x-(float(p.Front)+float(p.Rear))/2)<1e-6
    assert abs(sketch.Shape.BoundBox.Center.y)<1e-6
    assert abs(sketch.Shape.BoundBox.XLength-float(p.LogoWidth))<1e-6
    for obj in (base,sketch,profile_source):
        obj.Visibility=False
    relief.ViewObject.ShapeColor=(0.03,0.16,0.85)
    relief.ViewObject.LineColor=(0.02,0.05,0.18)

add_rdw_logo(doc)

def add_board_locks(doc):
    p=doc.Parameters
    end=float(p.ConnectorLength)+float(p.BoardLength)
    width=float(p.BoardWidth)
    x,y=float(p.FrontNotchX),float(p.FrontNotchY)
    radius=float(p.FrontNotchWidth)/2
    # The photographed front recesses are modelled as U-shaped cuts:
    # a semicircle plus a straight entry to the outer board edge.
    pcb=doc.PCB_Reference
    board=Part.makeBox(float(p.BoardLength),width,1,App.Vector(float(p.ConnectorLength),-width/2,-0.5))
    rear=Part.makeBox(float(p.RearNotchDepth)+0.1,float(p.RearNotchWidth),2,
        App.Vector(end-float(p.RearNotchDepth),-float(p.RearNotchWidth)/2,-1))
    board=board.cut(rear)
    for sign in (-1,1):
        round_cut=Part.makeCylinder(radius,2,App.Vector(x,sign*y,-1))
        ymin=y if sign>0 else -width/2-0.1
        entry=Part.makeBox(2*radius,width/2-y+0.1,2,App.Vector(x-radius,ymin,-1))
        board=board.cut(round_cut.fuse(entry))
    pcb.Shape=board.removeSplitter()
    pcb.Label='Printplaat met bevestigingsuitsparingen (afrondingen bij benadering)'
    sketch=rectangle(doc.Lower,'BoardLocks_Profile',42.1,-3.9,3,7.8,
        ['Parameters.ConnectorLength + Parameters.BoardLength - Parameters.RearNotchDepth + Parameters.Clearance',
         '-Parameters.RearNotchWidth / 2 + Parameters.Clearance',
         'Parameters.RearNotchDepth',
         'Parameters.RearNotchWidth - 2 * Parameters.Clearance'],
        '-Parameters.Height / 2 + Parameters.Wall')
    sketch.Label='Printverankering - nokkenprofiel'
    for sign in (-1,1):
        n=sketch.addGeometry(Part.Circle(App.Vector(x,sign*y,0),App.Vector(0,0,1),float(p.LockRadius)),False)
        for constraint,expr in [
            (Sketcher.Constraint('DistanceX',n,3,x),'Parameters.FrontNotchX'),
            (Sketcher.Constraint('DistanceY',n,3,sign*y),str(sign)+' * Parameters.FrontNotchY'),
            (Sketcher.Constraint('Radius',n,float(p.LockRadius)),'Parameters.LockRadius')]:
            index=sketch.addConstraint(constraint)
            sketch.setExpression('Constraints['+str(index)+']',expr)
    doc.recompute()
    base=doc.RDW_Relief
    pad=doc.Lower.newObject('PartDesign::Pad','BoardLocks')
    pad.Label='Printverankering - achterste nok en twee voorste nokken'
    pad.Profile=sketch
    pad.setExpression('Length','Parameters.LowerHeight - Parameters.Wall')
    doc.recompute()
    assert pad.Shape.isValid() and len(pad.Shape.Solids)==1
    assert sketch.FullyConstrained
    assert pad.Shape.common(pcb.Shape).Volume<1e-6
    base.Visibility=False
    sketch.Visibility=False
    pad.ViewObject.ShapeColor=(0.03,0.16,0.85)
    pad.ViewObject.LineColor=(0.02,0.05,0.18)

add_board_locks(doc)

def add_led_options(doc):
    settings=doc.addObject('App::FeaturePython','LED_Options')
    settings.Label='LED-opening - kies Stand'
    settings.addProperty('App::PropertyEnumeration','Stand','LED','Dicht, dun gesloten venster of open gat')
    settings.Stand=['Dicht','Dun venster','Open gat']
    settings.Stand='Dun venster'
    settings.addProperty('App::PropertyLength','Restdikte','LED','Dikte gesloten venster; kleiner dan wanddikte')
    settings.Restdikte=0.4
    settings.addProperty('App::PropertyLength','Diameter','LED','Diameter LED-opening')
    settings.Diameter=3
    settings.addProperty('App::PropertyLength','PositieX','LED','Vanaf connectortip; 40 mm is een schatting uit de foto')
    settings.PositieX=40
    settings.addProperty('App::PropertyDistance','PositieY','LED','Zijdelingse offset uit het midden')
    settings.PositieY=0
    settings.addProperty('App::PropertyLength','TekstVerschuiving','LED','Leon richting connector voor vrije ruimte boven LED')
    settings.TekstVerschuiving=2
    text=doc.Leon_Relief.Profile[0]
    expression=text.ExpressionEngine
    xexpr=next(expr for prop,expr in expression if prop.lstrip('.')=='Placement.Base.x')
    text.setExpression('Placement.Base.x','('+xexpr+') - LED_Options.TekstVerschuiving')
    sketch=doc.addObject('Sketcher::SketchObject','LED_Profile')
    sketch.Label='LED-opening - cirkelprofiel'
    doc.Upper.addObject(sketch)
    sketch.addGeometry(Part.Circle(App.Vector(40,0,0),App.Vector(0,0,1),1.5),False)
    index=sketch.addConstraint(Sketcher.Constraint('DistanceX',0,3,40))
    sketch.setExpression('Constraints['+str(index)+']','LED_Options.PositieX')
    index=sketch.addConstraint(Sketcher.Constraint('DistanceY',0,3,0))
    sketch.setExpression('Constraints['+str(index)+']','LED_Options.PositieY')
    index=sketch.addConstraint(Sketcher.Constraint('Radius',0,1.5))
    sketch.setExpression('Constraints['+str(index)+']','LED_Options.Diameter / 2')
    sketch.setExpression('Placement.Base.z','-Parameters.Height / 2 + Parameters.Wall')
    doc.recompute()
    pocket=doc.Upper.newObject('PartDesign::Pocket','LED_Opening')
    pocket.Label='LED-opening - schakelbaar'
    pocket.Profile=sketch
    pocket.setExpression('Length','LED_Options.Stand == 2 ? Parameters.Wall + 1 mm : Parameters.Wall - LED_Options.Restdikte')
    pocket.setExpression('Suppressed','LED_Options.Stand == 0')
    doc.recompute()
    sketch.Visibility=False
    doc.Leon_Relief.Visibility=False
    pocket.ViewObject.ShapeColor=(0.03,0.16,0.85)
    pocket.ViewObject.LineColor=(0.02,0.05,0.18)
    pocket.Visibility=True
    doc.Upper.Visibility=True
    assert pocket.Shape.isValid() and len(pocket.Shape.Solids)==1

add_led_options(doc)

def add_led_reference(doc):
    led=doc.addObject('Part::Box','LED_Reference')
    led.Label='LED - gele benadering (1,6 x 0,8 x 0,6 mm)'
    led.Length=1.6
    led.Width=0.8
    led.Height=0.6
    # Independent hardware reference: changing the window position must not
    # move the LED on the physical PCB. Position and size are estimates.
    led.Placement.Base=App.Vector(39.2,-0.4,0.5)
    led.addProperty('App::PropertyLink','Printplaat','Referentie','Bijbehorende referentieprint')
    led.Printplaat=doc.PCB_Reference
    doc.HardwareReference.addObject(led)
    led.ViewObject.ShapeColor=(1.0,0.85,0.0)
    led.ViewObject.LineColor=(0.5,0.35,0.0)
    led.Visibility=True
    doc.recompute()
    assert led.Shape.isValid() and len(led.Shape.Solids)==1
    assert led.Shape.distToShape(doc.PCB_Reference.Shape)[0]<1e-6
    assert led.Shape.common(doc.PCB_Reference.Shape).Volume<1e-6
    assert led.Shape.common(doc.Lower.Shape.fuse(doc.Upper.Shape)).Volume<1e-6
    return led

led=add_led_reference(doc)

def add_keyring_eye(doc):
    p=doc.Parameters
    def octagon(name,x0,x1,halfwidth,zexpr,corner,expressions):
        sketch=doc.addObject('Sketcher::SketchObject',name)
        doc.Lower.addObject(sketch)
        points=[(x0,-halfwidth+corner),(x0+corner,-halfwidth),
                (x1-corner,-halfwidth),(x1,-halfwidth+corner),
                (x1,halfwidth-corner),(x1-corner,halfwidth),
                (x0+corner,halfwidth),(x0,halfwidth-corner)]
        for i in range(8):
            a,b=points[i],points[(i+1)%8]
            sketch.addGeometry(Part.LineSegment(App.Vector(*a,0),App.Vector(*b,0)),False)
        for i in range(8):
            sketch.addConstraint(Sketcher.Constraint('Coincident',i,2,(i+1)%8,1))
            for axis,value,expr in [('DistanceX',points[i][0],expressions[i][0]),
                                    ('DistanceY',points[i][1],expressions[i][1])]:
                n=sketch.addConstraint(Sketcher.Constraint(axis,i,1,value))
                sketch.setExpression('Constraints['+str(n)+']',expr)
        sketch.setExpression('Placement.Base.z',zexpr)
        return sketch

    def profile_expressions(x0,x1,w,c):
        return [(x0,'-('+w+') + '+c),(x0+' + '+c,'-('+w+')'),
                (x1+' - '+c,'-('+w+')'),(x1,'-('+w+') + '+c),
                (x1,w+' - '+c),(x1+' - '+c,w),
                (x0+' + '+c,w),(x0,w+' - '+c)]
    x0='(Parameters.Rear - Parameters.Wall)'
    x1='(Parameters.Rear + Parameters.EyeExtension)'
    w='(Parameters.EyeWidth / 2)'
    c='Parameters.CornerChamfer'
    r=float(p.Rear)
    chamfer=float(p.CornerChamfer)
    outline=octagon('Keyring_Outline',r-float(p.Wall),r+float(p.EyeExtension),float(p.EyeWidth)/2,
        'Parameters.SeamHeight - Parameters.EyeThickness',chamfer,profile_expressions(x0,x1,w,c))
    outline.Label='Sleutelhangoog - gefacetteerde omtrek'
    base=doc.Lower.Tip
    pad=doc.Lower.newObject('PartDesign::Pad','Keyring_Pad')
    pad.Label='Sleutelhangoog - massieve verbinding'
    pad.Profile=outline
    pad.setExpression('Length','Parameters.EyeThickness')
    doc.recompute()
    assert pad.Shape.isValid() and len(pad.Shape.Solids)==1
    base.Visibility=False
    outline.Visibility=False
    center=r+float(p.EyeExtension)/2
    h=float(p.EyeHole)/2
    centerexpr='(Parameters.Rear + Parameters.EyeExtension / 2)'
    x0='('+centerexpr+' - Parameters.EyeHole / 2)'
    x1='('+centerexpr+' + Parameters.EyeHole / 2)'
    w='(Parameters.EyeHole / 2)'
    opening=octagon('Keyring_Opening',center-h,center+h,h,
        'Parameters.SeamHeight',chamfer,profile_expressions(x0,x1,w,c))
    opening.Label='Sleutelhangoog - achthoekige ringopening'
    pocket=doc.Lower.newObject('PartDesign::Pocket','Keyring_Eye')
    pocket.Label='Sleutelhangoog - 4,5 mm opening'
    pocket.Profile=opening
    pocket.setExpression('Length','Parameters.EyeThickness')
    doc.recompute()
    for sketch in (outline,opening):
        assert sketch.FullyConstrained
        sketch.Visibility=False
    pad.Visibility=False
    pocket.ViewObject.ShapeColor=(0.03,0.16,0.85)
    pocket.ViewObject.LineColor=(0.02,0.05,0.18)
    assert pocket.Shape.isValid() and len(pocket.Shape.Solids)==1
    assert base.Shape.cut(pocket.Shape).Volume<1e-6
    bore=Part.makeCylinder(float(p.EyeHole)/2,float(p.EyeThickness),
        App.Vector(center,0,float(p.SeamHeight)-float(p.EyeThickness)))
    assert pocket.Shape.common(bore).Volume<1e-6

add_keyring_eye(doc)

for body in (lower,upper):
    assert body.Shape.isValid(), body.Name+' invalid'
    assert len(body.Shape.Solids)==1, body.Name+' not one solid'
    for obj in body.Group:
        if obj.TypeId=='Sketcher::SketchObject':
            assert obj.FullyConstrained
assert lower.Shape.common(upper.Shape).Volume < 1e-6
assert float(p.RetentionOverlap) > float(p.Clearance)
locks=doc.BoardLocks.Shape.cut(doc.RDW_Relief.Shape).removeSplitter()
assert len(locks.Solids)==3
for lock in locks.Solids:
    assert lock.distToShape(pcb.Shape)[0]>=float(p.Clearance)-1e-6
for direction in (-1,1):
    moved=pcb.Shape.copy()
    moved.translate(App.Vector(direction*(float(p.Clearance)+0.05),0,0))
    assert locks.common(moved).Volume>1e-6
assert lower.Shape.common(doc.USB_A_Reference.Shape).Volume<1e-6
envelope_matrix=App.Matrix()
envelope_matrix.A33=4
assert lower.Shape.fuse(upper.Shape).common(pcb.Shape.transformGeometry(envelope_matrix)).Volume<1e-6
# The PCB front shoulder must hit the LOWER front wall after axial play is used.
for dy in (-float(p.Clearance), 0, float(p.Clearance)):
    for dz in (-float(p.Clearance), 0, float(p.Clearance)):
        pulled=pcb.Shape.copy()
        pulled.translate(App.Vector(-float(p.FrontClearance)-0.05,dy,dz))
        assert lower.Shape.common(pulled).Volume > 1e-6
print('Buitenmaat inclusief sleutelhangoog:',float(p.Length+p.EyeExtension),float(p.Width),float(p.Height))
print('Vrije connector:',float(p.Front),'mm')
print('Solids and validity:',[(b.Name,len(b.Shape.Solids),b.Shape.isValid(),b.Shape.Volume) for b in (lower,upper)])

Gui.Selection.clearSelection()
def save_preview(filename,width=1600,height=1000,background='White'):
    Gui.updateGui()
    Gui.activeDocument().activeView().redraw()
    Gui.activeDocument().activeView().saveImage(filename,width,height,background)

view=Gui.activeDocument().activeView()
animation_enabled=view.isAnimationEnabled()
view.setAnimationEnabled(False)
Gui.activeDocument().activeView().viewAxonometric()
Gui.activeDocument().activeView().fitAll()
save_preview(os.path.join(IMAGES,'FreeCAD-assemblage.png'))
saved_mode=doc.LED_Options.Stand
doc.LED_Options.Stand='Open gat'
doc.recompute()
save_preview(os.path.join(IMAGES,'FreeCAD-LED-open.png'))
doc.LED_Options.Stand=saved_mode
doc.recompute()
Gui.activeDocument().activeView().viewBottom()
Gui.activeDocument().activeView().fitAll()
save_preview(os.path.join(IMAGES,'FreeCAD-onderkant.png'))
Gui.activeDocument().activeView().viewAxonometric()
upper.Visibility=False
pcb.Visibility=True
led.Visibility=True
Gui.activeDocument().activeView().fitAll()
save_preview(os.path.join(IMAGES,'FreeCAD-binnenkant.png'))
pcb.Visibility=False
led.Visibility=False
save_preview(os.path.join(IMAGES,'FreeCAD-verankering.png'))
pcb.Visibility=True
led.Visibility=True
upper.Visibility=True
upper.Placement.Base.z=7
Gui.activeDocument().activeView().fitAll()
save_preview(os.path.join(IMAGES,'FreeCAD-exploded.png'))
upper.Placement.Base.z=0
pcb.Visibility=True
led.Visibility=True
Gui.activeDocument().activeView().fitAll()
view.setAnimationEnabled(animation_enabled)
doc.recompute()
doc.saveAs(os.path.join(ROOT,'USB-behuizing.FCStd'))

# Both parts have their seam on the bed and the raised artwork facing upwards.
for body,filename in [(lower,'onderhelft'),(upper,'bovenhelft')]:
    shape=body.Tip.Shape.copy()
    shape.Placement=App.Placement()
    shape.rotate(App.Vector(),App.Vector(1,0,0),180)
    bounds=shape.BoundBox
    shape.translate(App.Vector(-bounds.XMin,-bounds.YMin,-bounds.ZMin))
    mesh=MeshPart.meshFromShape(Shape=shape,LinearDeflection=0.05,AngularDeflection=math.radians(15),Relative=False)
    assert mesh.isSolid()
    assert abs(mesh.BoundBox.ZMin)<1e-6
    mesh.write(os.path.join(EXPORTS,filename+'.stl'))
Part.export([lower,upper],os.path.join(EXPORTS,'USB-behuizing.step'))
print('Saved FCStd to', ROOT, '; STEP and STL to', EXPORTS, '; screenshot to', IMAGES)
