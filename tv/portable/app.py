from xml.dom.minidom import parse, parseString
import sys
import frontend
import template
import database
import item
import downloader
import re
import random
import copy
import resource
import cgi
import types
import feed
import traceback
import config
import datetime
import autodler
import folder
import scheduler

db = database.defaultDatabase

###############################################################################
#### The main application controller object, binding model to view         ####
###############################################################################

class Controller(frontend.Application):
    def __init__(self):
	frontend.Application.__init__(self)

    ### Startup and shutdown ###

    def onStartup(self):
	try:
	    # NEEDS: Set backend delegate with something like:
	    # backend.setDelegate(self.getBackendDelegate())

	    #Restoring
	    print "DTV: Restoring database..."
	    db.restore()
	    print "DTV: Recomputing filters..."
	    db.recomputeFilters()

	    # Define variables for templates
	    # NEEDS: reorganize this, and update templates
	    globalData = {
		'database': db,
		'filter': globalFilterList,
		'sort': globalSortList,
		}
	    tabPaneData = {
		'global': globalData,
		}

	    # Set up tab list
	    reloadStaticTabs()
	    mapFunc = makeMapToTabFunction(globalData, self)
	    self.tabs = db.filter(mappableToTab).map(mapFunc).sort(sortTabs)
	    self.currentSelectedTab = None
	    self.tabListActive = True
	    tabPaneData['tabs'] = self.tabs

	    # Put cursor on first tab to indicate that it should be initially
	    # selected
	    self.tabs.resetCursor()
	    self.tabs.getNext()

	    # If there are no feeds in the database, create a test feed
	    hasFeed = False
	    for obj in db.objects:
		if obj[0].__class__.__name__ == 'RSSFeed':
		    hasFeed = True
		    break
	    #if not hasFeed:
		#print "Spawning first feed..."
		#f = feed.RSSFeed("http://blogtorrent.com/demo/rss.php")
		#fold = folder.Folder('Test folder')
		#fold.addFeed(f)

	    # If we're missing the file system videos feed, create it
	    hasDirFeed = False
	    for obj in db.objects:
		if obj[0].__class__.__name__ == 'DirectoryFeed':
		    hasDirFeed = True
		    break
	    if not hasDirFeed:
		print "DTV: Spawning file system videos feed"
		d = feed.DirectoryFeed()
	    
	    # Start the automatic downloader daemon
	    print "DTV: Spawning auto downloader..."
	    autodler.AutoDownloader()

	    # Put up the main frame
	    print "DTV: Displaying main frame..."
	    self.frame = frontend.MainFrame(self)

	    # Set up tab list (on left); this will automatically set up the
	    # display area (on right) and currentSelectedTab
	    self.tabDisplay = TemplateDisplay('tablist', tabPaneData, self)
	    self.frame.selectDisplay(self.tabDisplay, 0)
	    self.tabs.addRemoveCallback(lambda oldObject, oldIndex: self.checkSelectedTab())
	    self.checkSelectedTab()
	    
	    # NEEDS: our strategy above with addRemoveCallback doesn't
	    # work. I'm not sure why, but it seems to have to do with the
	    # reentrant call back into the database when checkSelectedTab ends 
	    # up calling endChange to force a tab to get rerendered.

	except:
	    print "DTV: Exception on startup:"
	    traceback.print_exc()
	    sys.exit(1)

    def onShutdown(self):
	try:
	    print "DTV: Stopping scheduler"
	    scheduler.ScheduleEvent.scheduler.shutdown()

	    print "DTV: Removing static tabs..."
	    db.removeMatching(lambda x:str(x.__class__.__name__) == "StaticTab")
	    # for item in db:
	    #    print str(item.__class__.__name__) + " of id "+str(item.getID())
	    print "DTV: Saving database..."
	    db.save()

	    # FIXME closing BitTorrent is slow and makes the application seem hung...
	    print "DTV: Shutting down BitTorrent..."
	    downloader.shutdownBTDownloader()

	    print "DTV: Done shutting down."

	except:
	    print "DTV: Exception on shutdown:"
	    traceback.print_exc()
	    sys.exit(1)

    ### Handling events received from the OS (via our base class) ###

    # Called by Frontend via Application base class in response to OS request.
    def addAndSelectFeed(self, url, showTemplate = None):
	return GUIActionHandler(self).addFeed(url, showTemplate)

    ### Keeping track of the selected tab and showing the right template ###

    def getTabState(self, tabId):
	# Determine if this tab is selected
	isSelected = False
	if self.currentSelectedTab:
	    isSelected = (self.currentSelectedTab.id == tabId)

	# Compute status string
	if isSelected:
	    if self.tabListActive:
		return 'selected'
	    else:
		return 'selected-inactive'
	else:
	    return 'normal'

    def checkSelectedTab(self, templateNameHint = None):
	# NEEDS: locking ...
	# NEEDS: ensure is reentrant (as in two threads calling it simultaneously by accident)

	# We'd like to track the currently selected tab entirely with
	# the cursor on self.tabs. Alas, it is not to be -- when
	# getTabState is called from the database code in response to
	# a change to a tab object (say), the cursor has been
	# temporarily moved by the database code. Long-term, we should
	# make the database code not do this. But short-term, we track
	# the the currently selected tab separately too, synchronizing
	# it to the cursor here. This isn't really wasted effort,
	# because this variable is also the mechanism by which we
	# check to see if the cursor has moved since the last call to
	# checkSelectedTab.
	#
	# Why use the cursor at all? It's necessary because we want
	# the database code to handle moving the cursor on a deleted
	# record automatically for us.

	oldSelected = self.currentSelectedTab
	newSelected = self.tabs.cur()
	self.currentSelectedTab = newSelected 

	tabChanged = ((oldSelected == None) != (newSelected == None)) or (oldSelected and newSelected and oldSelected.id != newSelected.id)
	if tabChanged: # Tab selection has changed! Deal.

	    # Redraw the old and new tabs
	    if oldSelected:
		oldSelected.redraw()
	    if newSelected:
		newSelected.redraw()

	    # Boot up the new tab's template.
	    if newSelected:
		newSelected.start(self.frame, templateNameHint)
	    else:
		self.selectDisplay(NullDisplay())

    def setTabListActive(self, active):
	"""If active is true, show the tab list normally. If active is
	false, show the tab list a different way to indicate that it
	doesn't pertain directly to what is going on (for example, a
	video is playing) but that it can still be clicked on."""
	self.tabListActive = active
	if self.tabs.cur():
	    self.tabs.cur().redraw()

def main():
    Controller().Run()

###############################################################################
#### TemplateDisplay: a HTML-template-driven right-hand display panel      ####
###############################################################################

class TemplateDisplay(frontend.HTMLDisplay):

    def __init__(self, templateName, data, controller, frameHint=None, indexHint=None):
	"'templateName' is the name of the inital template file. 'data' is keys for the template."

	self.controller = controller
	self.templateName = templateName
	self.templateData = data
	(html, self.templateHandle) = template.fillTemplate(templateName, data, lambda js:self.execJS(js))

	self.actionHandlers = [
	    ModelActionHandler(),
	    GUIActionHandler(self.controller),
	    TemplateActionHandler(self.controller, self, self.templateHandle),
	    ]

 	frontend.HTMLDisplay.__init__(self, html, frameHint=frameHint, indexHint=indexHint)

    def onURLLoad(self, url):
	try:
	    # Special-case non-'action:'-format URL
	    match = re.compile(r"^template:(.*)$").match(url)
	    if match:
		self.dispatchAction('switchTemplate', name = match.group(1))
		return False

	    # Standard 'action:' URL
	    match = re.compile(r"^action:([^?]+)\?(.*)$").match(url)
	    if match:
		action = match.group(1)
		argString = match.group(2)
		argLists = cgi.parse_qs(argString, keep_blank_values=True)

		# argLists is a dictionary from parameter names to a list
		# of values given for that parameter. Take just one value
		# for each parameter, raising an error if more than one
		# was given.
		args = {}
		for key in argLists.keys():
		    value = argLists[key]
		    if len(value) != 1:
			raise template.TemplateError, "Multiple values of '%s' argument passend to '%s' action" % (key, action)
		    args[key] = value[0]

		if self.dispatchAction(action, **args):
		    return False
		else:
		    print "Ignored bad action URL: %s" % url
		    return False

	except:
	    print "Exception in URL action handler (for URL '%s'):" % url
	    traceback.print_exc()
	    sys.exit(1)

	return True

    def dispatchAction(self, action, **kwargs):
	for handler in self.actionHandlers:
	    if hasattr(handler, action):
		getattr(handler, action)(**kwargs)
		return True

	return False

###############################################################################
#### Handlers for actions generated from templates, the OS, etc            ####
###############################################################################

# Functions that are safe to call from action: URLs that do nothing
# but manipulate the database.
class ModelActionHandler:
    def changeFeedSettings(self, myFeed, maxnew, fallbehind, automatic, exprieDays, expireHours, expire, getEverything):
	
	db.beginUpdate()
	db.saveCursor()
	try:
	    for obj in db:
		if obj.getID() == int(myFeed):
		    obj.saveSettings(automatic,maxnew,fallbehind,expire,expireDays,expireHours,getEverything)
		    break
	finally:
	    db.restoreCursor()
	    db.endUpdate()
	
    def playFile(self, filename):
	print "Playing "+filename
	# Use a quick hack to play the file. (NEEDS)
	frontend.playVideoFileHack(filename)

    def startDownload(self, item):
	db.beginUpdate()
	db.saveCursor()
	try:
	    for obj in db:
		if obj.getID() == int(item):
		    obj.download()
		    break
	finally:
	    db.restoreCursor()
	    db.endUpdate()

    def removeFeed(self, url):
	db.beginUpdate()
	try:
	    db.removeMatching(lambda x: isinstance(x,feed.Feed) and x.getURL() == url)
	finally:
	    db.endUpdate()

    def stopDownload(self, item):
	db.beginUpdate()
	db.saveCursor()
	try:
	    for obj in db:
		if obj.getID() == int(item):
		    obj.stopDownload()
		    break
	finally:
	    db.restoreCursor()
	    db.endUpdate()

    # Collections

    def addCollection(self, title):
	x = feed.Collection(title)

    def removeCollection(self, id):
	db.beginUpdate()
	db.removeMatching(lambda x: isinstance(x, feed.Collection) and x.getID() == int(id))
	db.endUpdate()

    def addToCollection(self, id, item):
	db.beginUpdate()
	try:

	    obj = None
	    for x in db:
		if isinstance(x,feed.Collection) and x.getID() == int(id):
		    obj = x
		    break
	
	    if obj != None:
		for x in db:
		    if isinstance(x,item.Item) and x.getID() == int(item):
			obj.addItem(x)

	finally:
	    db.endUpdate()

    def removeFromCollection(self, id, item):
	db.beginUpdate()
	try:

	    obj = None
	    for x in db:
		if isinstance(x,feed.Collection) and x.getID() == int(id):
		    obj = x
		    break

	    if obj != None:
		for x in db:
		    if isinstance(x,item.Item) and x.getID() == int(item):
			obj.removeItem(x)

	finally:
	    db.endUpdate()

    def moveInCollection(self, id, item, pos):
	db.beginUpdate()
	try:

	    obj = None
	    for x in db:
		if isinstance(x,feed.Collection) and x.getID() == int(id):
		    obj = x
		    break

	    if obj != None:
		for x in db:
		    if isinstance(x,item.Item) and x.getID() == int(item):
			obj.moveItem(x,int(pos))

	finally:
	    db.endUpdate()

    # Following are just for debugging/testing.

    def deleteTab(self, base):
	db.beginUpdate()
	try:
	    db.removeMatching(lambda x: isinstance(x, StaticTab) and x.tabTemplateBase == base)
	finally:
	    db.endUpdate()
    
    def createTab(self, tabTemplateBase, contentsTemplate, order):
	db.beginUpdate()
	try:
	    order = int(order)
	    StaticTab(tabTemplateBase, contentsTemplate, order)
	finally:
	    db.endUpdate()

    def recomputeFilters(self):
	db.recomputeFilters()

# Functions that are safe to call from action: URLs that can change
# the GUI presentation (and may or may not manipulate the database.)
class GUIActionHandler:
    def __init__(self, controller):
	self.controller = controller

    def selectTab(self, id, templateNameHint = None):
	db.beginRead()
	# NEEDS: lock on controller state
	
	try:
	    # Move the cursor to the newly selected object
	    self.controller.tabs.resetCursor()
	    while True:
		cur = self.controller.tabs.getNext()
		if cur == None:
		    assert(0) # NEEDS: better error (JS sent bad tab id)
		if cur.id == id:
		    break

	finally:
	    db.endRead() # NEEDS: dropping this prematurely?

	# Figure out what happened
	oldSelected = self.controller.currentSelectedTab
	newSelected = self.controller.tabs.cur()

	# Handle reselection action (checkSelectedTab won't; it doesn't
	# see a difference)
	if oldSelected and oldSelected.id == newSelected.id:
	    newSelected.start(self.controller.frame, templateNameHint)

	# Handle case where a different tab was clicked
	self.controller.checkSelectedTab(templateNameHint)

    # NEEDS: name should change to addAndSelectFeed; then we should create
    # a non-GUI addFeed to match removeFeed. (requires template updates)

    def addFeed(self, url, showTemplate = None):
	db.beginUpdate()
	db.saveCursor()

	try:
	    exists = False
	    for obj in db:
		if isinstance(obj,feed.Feed) and obj.getURL() == url:
		    exists = True
		    break
		
	    if not exists:
		myFeed = feed.RSSFeed(url)

		# At this point, the addition is guaranteed to be reflected
		# in the tab list.

		tabs = self.controller.tabs
		tabs.resetCursor()
		while True:
		    cur = tabs.getNext()
		    if cur == None:
			assert(0) # NEEDS: better error (failed to add tab)
		    if cur.feedURL() == url:
			break

		self.controller.checkSelectedTab(showTemplate)

	finally:
	    db.restoreCursor()
	    db.endUpdate()

# Functions that are safe to call from action: URLs that change state
# specific to a particular instantiation of a template, and so have to
# be scoped to a particular HTML display widget.
class TemplateActionHandler:
    def __init__(self, controller, display, templateHandle):
	self.controller = controller
	self.display = display
	self.templateHandle = templateHandle

    def switchTemplate(self, name):
	# Graphically indicate that we're not at the home
	# template anymore
	self.controller.setTabListActive(False)

	# Switch to new template. It get the same variable
	# dictionary as we have.
	# NEEDS: currently we hardcode the display index. This means
	# that these links always affect the right-hand 'content'
	# area, even if they are loaded from the left-hand 'tab'
	# area. Actually this whole invocation is pretty hacky.
	self.controller.frame.selectDisplay(TemplateDisplay(name, self.display.templateData, self.controller, frameHint=self.controller.frame, indexHint=1), 1)

    def setViewFilter(self, viewName, fieldKey, functionKey, parameter, invert):
	invert = stringToBoolean(invert)
	namedView = self.templateHandle.findNamedView(viewName)
	namedView.setFilter(fieldKey, functionKey, parameter, invert)
	db.recomputeFilters()

    def setViewSort(self, viewName, fieldKey, functionKey, reverse):
	reverse = stringToBoolean(reverse)
	namedView = self.templateHandle.findNamedView(viewName)
	namedView.setSort(fieldKey, functionKey, reverse)
	db.recomputeFilters()
	
    def playView(self, viewName, firstItemId):
	# Find the database view that we're supposed to be
	# playing; take out items that aren't playable video
	# clips and put it in the format the frontend expects.
	namedView = self.templateHandle.findNamedView(viewName)
	view = namedView.getView()
	view = view.filter(mappableToPlaylistItem)
	view = view.map(mapToPlaylistItem)

	# Move the cursor to the requested item; if there's no
	# such item in the view, move the cursor to the first
	# item
	db.beginRead()
	try:
	    view.resetCursor()
	    while True:
		cur = view.getNext()
		if cur == None:
		    # Item not found in view. Put cursor at the first
		    # item, if any.
		    view.resetCursor()
		    view.getNext()
		    break
		if str(cur.getID()) == firstItemId:
		    # The cursor is now on the requested item.
		    break
	finally:
	    db.endRead()
	    
	# Construct playback display and switch to it, arranging
	# to switch back to ourself when playback mode is exited
	self.controller.frame.selectDisplay(frontend.VideoDisplay(view, self.display), 1)

# Helper: liberally interpret the provided string as a boolean
def stringToBoolean(string):
    if string == "" or string == "0" or string == "false":
	return False
    else:
	return True

###############################################################################
#### Tabs                                                                  ####
###############################################################################

class Tab:
    idCounter = 0

    def __init__(self, tabTemplateBase, tabData, contentsTemplate, contentsData, sortKey, obj, controller):
	self.tabTemplateBase = tabTemplateBase
	self.tabData = tabData
	self.contentsTemplate = contentsTemplate
	self.contentsData = contentsData
	self.sortKey = sortKey
	self.controller = controller
	self.id = "tab%d" % Tab.idCounter
	Tab.idCounter += 1
	self.obj = obj

    def start(self, frame, templateNameHint):
	self.controller.setTabListActive(True) 
	# '1' means 'right hand side of the window, in the display area.'
	frame.selectDisplay(TemplateDisplay(templateNameHint or self.contentsTemplate, self.contentsData, self.controller, frameHint=frame, indexHint=1), 1)
    
    def markup(self):
	"""Get HTML giving the visual appearance of the tab. 'state' is
	one of 'selected' (tab is currently selected), 'normal' (tab is
	not selected), or 'selected-inactive' (tab is selected but
	setTabListActive was called with a false value on the MainFrame
	for which the tab is being rendered.) The HTML should be returned
	as a xml.dom.minidom element or document fragment."""
	state = self.controller.getTabState(self.id)
	file = "%s-%s" % (self.tabTemplateBase, state)
	return template.fillStaticTemplate(file, self.tabData)
	
    def redraw(self):
	# Force a redraw by sending a change notification on the underlying
	# DB object.
	self.obj.beginChange()
	self.obj.endChange()

    def isFeed(self):
	"""True if this Tab represents a Feed."""
	return isinstance(self.obj, feed.Feed)

    def feedURL(self):
	"""If this Tab represents a Feed, the feed's URL. Otherwise None."""
	if isinstance(self.obj, feed.Feed):
	    return self.obj.getURL()
	else:
	    return None	

# Database object representing a static (non-feed-associated) tab.
class StaticTab(database.DDBObject):
    def __init__(self, tabTemplateBase, contentsTemplate, order):
	self.tabTemplateBase = tabTemplateBase
	self.contentsTemplate = contentsTemplate
	self.order = order
	database.DDBObject.__init__(self)

# Reload the StaticTabs in the database from the statictabs.xml resource file.
def reloadStaticTabs():
    db.beginUpdate()
    try:
	# Wipe all of the StaticTabs currently in the database.
	db.removeMatching(lambda x: x.__class__ == StaticTab)

	# Load them anew from the resource file.
	# NEEDS: maybe better error reporting?
	document = parse(resource.path('statictabs.xml'))
	for n in document.getElementsByTagName('statictab'):
	    tabTemplateBase = n.getAttribute('tabtemplatebase')
	    contentsTemplate = n.getAttribute('contentstemplate')
	    order = int(n.getAttribute('order'))
	    StaticTab(tabTemplateBase, contentsTemplate, order)
    finally:
	db.endUpdate()

# Return True if a tab should be shown for obj in the frontend. The filter
# used on the database to get the list of tabs.
def mappableToTab(obj):
    return isinstance(obj, StaticTab) or isinstance(obj, folder.Folder) or (isinstance(obj, feed.Feed) and obj.isVisible())

# Generate a function that, given an object for which mappableToTab
# returns true, return a Tab instance -- mapping a model object into
# a UI objet that can be rendered and selected.
#
# By 'generate a function', we mean that you give makeMapToTabFunction
# the global data that you want to always be available in both the tab
# templates and the contents page template, and it returns a function
# that maps objects to tabs such that that request is satisified.
def makeMapToTabFunction(globalTemplateData, controller):
    class MapToTab:
	def __init__(self, globalTemplateData):
	    self.globalTemplateData = globalTemplateData
	
	def mapToTab(self,obj):
	    data = {'global': self.globalTemplateData};
	    if isinstance(obj, StaticTab):
		return Tab(obj.tabTemplateBase, data, obj.contentsTemplate, data, [obj.order], obj, controller)
	    elif isinstance(obj, feed.Feed):
	    	data['feed'] = obj
		# Change this to sort feeds on a different value
		sortKey = obj.getTitle()
	    	return Tab('feedtab', data, 'feed-start', data, [100, sortKey], obj, controller)
	    elif isinstance(obj, folder.Folder):
		data['folder'] = obj
		sortKey = obj.getTitle()
		return Tab('foldertab',data,'folder',data,[500,sortKey],obj,controller)
	    else:
		assert(0) # NEEDS: clean up (signal internal error)

    return MapToTab(globalTemplateData).mapToTab

# The sort function used to order tabs in the tab list: just use the
# sort keys provided when mapToTab created the Tabs. These can be
# lists, which are tested left-to-right in the way you'd
# expect. Generally, the way this is used is that static tabs are
# assigned a numeric priority, and get a single-element list with that
# number as their sort key; feeds get a list with '100' in the first
# position, and a value that determines the order of the feeds in the
# second position. This way all of the feeds are together, and the
# static tabs can be positioned around them.
def sortTabs(x, y):
    if x.sortKey < y.sortKey:
	return -1
    elif x.sortKey > y.sortKey:
	return 1
    return 0

###############################################################################
#### Video clips                                                           ####
###############################################################################

def mappableToPlaylistItem(obj):
    if not isinstance(obj, item.Item):
	return False
    # NEEDS: check to see if the download has finished in a cleaner way
    if obj.downloadState() != "finished":
	return False
    return True

class playlistItemFromItem(frontend.PlaylistItem):
    def __init__(self, item):
	self.item = item

    def getTitle(self):
	# NEEDS
	return "Title here"

    def getPath(self):
	# NEEDS
	return "/Users/gschmidt/Movies/mahnamahna.mpeg"

    def getLength(self):
	# NEEDS
	return 42.42

    def onViewed(self):
	# NEEDS: I have no idea if this is right.
	#self.item.markItemSeen()
	None

    # Return the ID that is used by a template to indicate this item 
    def getID(self):
	return self.item.getID()

def mapToPlaylistItem(obj):
    return playlistItemFromItem(obj)

###############################################################################
#### The global set of filter and sort functions accessible from templates ####
###############################################################################

def compare(x, y):
    if x < y:
	return -1
    if x > y:
	return 1
    return 0

def itemSort(x,y):
    if x.getReleaseDate() < y.getReleaseDate():
	return -1
    elif x.getReleaseDate() > y.getReleaseDate():
	return 1
    elif x.getID() < y.getID():
	return -1
    elif x.getID() > y.getID():
	return 1
    else:
	return 0

def alphabeticalSort(x,y):
    if x.getTitle() < y.getTitle():
	return -1
    elif x.getTitle() > y.getTitle():
	return 1
    elif x.getDescription() < y.getDescription():
	return -1
    elif x.getDescription() > y.getDescription():
	return 1
    else:
	return 0

def downloadStartedSort(x,y):
    if x.getTitle() < y.getTitle():
	return -1
    elif x.getTitle() > y.getTitle():
	return 1
    elif x.getDescription() < y.getDescription():
	return -1
    elif x.getDescription() > y.getDescription():
	return 1
    else:
	return 0

globalSortList = {
    'item': itemSort,
    'alphabetical': alphabeticalSort,
    'downloadStarted': downloadStartedSort,
    'text': (lambda x, y: compare(str(x), str(y))),
    'number': (lambda x, y: compare(float(x), float(y))),
}

def filterClass(obj, parameter):
    if type(obj) != types.InstanceType:
	return False

    # Pull off any package name
    name = str(obj.__class__)
    match = re.compile(r"\.([^.]*)$").search(name)
    if match:
	name = match.group(1)

    return name == parameter

def filterHasKey(obj,parameter):
    try:
	obj[parameter]
    except KeyError:
	return False
    return True

globalFilterList = {
    'substring': (lambda x, y: str(y) in str(x)),
    'boolean': (lambda x, y: x),

    #FIXME make this look at the feed's time until expiration
    'recentItems': (lambda x, y: isinstance(x,item.Item) and x.getState() == 'finished' and x.getDownloadedTime()+config.get('DefaultTimeUntilExpiration')>datetime.datetime.now() and (str(y).lower() in x.getTitle().lower() or str(y).lower() in x.getDescription().lower())),
    'oldItems': (lambda x, y:  isinstance(x,item.Item) and x.getState() == 'finished' and x.getDownloadedTime()+config.get('DefaultTimeUntilExpiration')<=datetime.datetime.now() and (str(y).lower() in x.getTitle().lower() or str(y).lower() in x.getDescription().lower())),

    'downloadedItems': (lambda x, y: isinstance(x,item.Item) and x.getState() == 'finished' and (str(y).lower() in x.getTitle().lower() or str(y).lower() in x.getDescription().lower())),
    'unDownloadedItems': (lambda x, y: isinstance(x,item.Item) and (not x.getState() == 'finished') and (str(y).lower() in x.getTitle().lower() or str(y).lower() in x.getDescription().lower())),
    'downloadingItems': (lambda x, y: isinstance(x,item.Item) and x.getState() == 'downloading' and (str(y).lower() in x.getTitle().lower() or str(y).lower() in x.getDescription().lower())),
       
    'class': filterClass,
    'all': (lambda x, y: True),
    'hasKey':  filterHasKey,
}
