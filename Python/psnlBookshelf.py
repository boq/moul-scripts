""" *==LICENSE==*

CyanWorlds.com Engine - MMOG client, server and tools
Copyright (C) 2011  Cyan Worlds, Inc.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

You can contact Cyan Worlds, Inc. by email legal@cyan.com
 or by snail mail at:
      Cyan Worlds, Inc.
      14617 N Newport Hwy
      Mead, WA   99021

 *==LICENSE==* """

"""
Module: psnlBookshelf
Age: Personal Age
Date: August 2002
Author: Bill Slease
This is the handler for the standard personal age bookshelf
Interfaces with xLinkingBookGUIPopup.py
"""

from Plasma import *
from PlasmaTypes import *
from PlasmaNetConstants import PtLinkingRules

import PlasmaKITypes
import PlasmaControlKeys

# define the attributes that will be entered in max
#PALGUI = ptAttribGUIDialog(2,"The PAL GUI")
actBookshelf = ptAttribActivator(3, "Actvtr:Bookshelf")

actBook = ptAttribActivator(4, "Actvtr:Book", byObject = 1)
respPresentBook = ptAttribResponder(5, "Rspndr:PresentBook", byObject = 1)
respShelveBook = ptAttribResponder(6, "Rspndr:ShelveBook", byObject = 1)
objLibrary = ptAttribSceneobjectList(7, "Objct:Books")

objTrays = ptAttribSceneobjectList(8, "Objct:Trays")
respDeleteBook = ptAttribResponder(9, "Rspndr:DeleteBook", byObject = 1)
respReturnTray = ptAttribResponder(10, "Rspndr:ReturnTray", byObject = 1)
actTray = ptAttribActivator(11, "Actvtr:Tray", byObject = 1)

objLocks = ptAttribSceneobjectList(12, "Objct:Locks")
respOpenLock = ptAttribResponder(13, "Rspndr:OpenLock", byObject = 1)
respCloseLock = ptAttribResponder(14, "Rspndr:CloseLock", byObject = 1)
actLock = ptAttribActivator(15, "Actvtr:Lock", byObject = 1)

#animLockOpen = ptAttribAnimation(16, "open clasp anim", byObject = 1)
#animLockClose = ptAttribAnimation(17, "close clasp anim", byObject = 1)

seekBehavior = ptAttribBehavior(18, "Smart seek before GUI") # used to make user walk in front of shelf before using it
shelfCamera = ptAttribSceneobject(19, "Bookshelf camera") # the camera used when engaging the shelf
respRaiseShelfClickable = ptAttribResponder(20, "Rspndr:Raise Clickable (LocalOnly)", netForce = 0) # Bill's sneaky way to: 1) engage the bookshelf, and 2) keep others from using a shelf already in use by making it's movement "LocalOnly" in Maxs user properties
respLowerShelfClickable = ptAttribResponder(21, "Rspndr:Lower Clickable") #undoes the damage in previous step
actDisengageShelf = ptAttribActivator(22, "Actvtr: Disengage Shelf") # region detector around the SeekBehavior node (#18 above) which detects when a player walks away from the shelf. Only disengages if "exiter" is the current user
HutCamera = ptAttribSceneobject(23, "Hut circle camera") # the camera which was used before engaging the shelf

actLinkingBookGUIPopup = ptAttribNamedActivator(24, "Actvr: LinkingBook GUI") # incoming notifies from the open Linking Book GUI

actBookshelfExit = ptAttribActivator(25, "Actvr: Exit bookshelf")

def getAgeDataFolder():
    """"Find folder named 'AgeData' in current age info node or create new"""
    ageVault = ptAgeVault()
    ageInfoNode = ageVault.getAgeInfo()
    ageInfoChildren = ageInfoNode.getChildNodeRefList()
    for ageInfoChildRef in ageInfoChildren:
        ageInfoChild = ageInfoChildRef.getChild()
        folder = ageInfoChild.upcastToFolderNode()
        if folder and folder.folderGetName() == "AgeData":
            return folder

    #no folder found
    folder = ptVaultFolderNode(0)
    folder.folderSetName("AgeData")
    ageInfoNode.addNode(folder)

    return folder

def getAgeDataChronicle(name, defaultValue, canCreate = True):
    """Find chronicle node in AgeData folder of current age or create new with default value"""
    folder = getAgeDataFolder()
    ageDataChildren = folder.getChildNodeRefList()
    for ageDataChildRef in ageDataChildren:
        ageDataChild = ageDataChildRef.getChild()
        chron = ageDataChild.upcastToChronicleNode()
        if chron and chron.getName() == name:
            return chron

    if not canCreate:
        return False

    #not found, create new
    chron = ptVaultChronicleNode(0)
    chron.setName(name)
    chron.setValue(str(int(defaultValue)))
    folder.addNode(chron)
    return chron

def ageDataChronicles():
    folder = getAgeDataFolder()
    ageDataChildren = folder.getChildNodeRefList()
    for ageDataChildRef in ageDataChildren:
        ageDataChild = ageDataChildRef.getChild()
        chron = ageDataChild.upcastToChronicleNode()
        if chron:
            yield chron

class Book(object):
    # Basic book functionality
    def __init__(self, index, unlockable = True, deletable = True):
        self.index = index
        self.unlockable = unlockable
        self.deletable = deletable
        self.ageFilename = None
        self.linkNode = None
        self.visible = True

    def setLinkNode(self, ageLinkNode):
        # We save it here, assuming that it will be immutable for whole Book object lifetime
        # I think it's ok to do that, since relto owner (and anyone else) can't delete or change
        # link to age on bookshelf during its operation
        self.linkNode = ageLinkNode
        self.ageFilename = ageLinkNode.getAgeInfo().getAgeFilename()

    @property
    def locked(self):
        return self.linkNode.getLocked()

    @locked.setter
    def locked(self, value):
        self.linkNode.setLocked(value)
        self.linkNode.save()

    @property
    def volatile(self):
        return self.linkNode.getVolatile()

    @volatile.setter
    def volatile(self, value):
        self.linkNode.setVolatile(value)
        self.linkNode.save()

    deleteConfirmText = "Personal.Bookshelf.DeleteBook"

    #called on tray use, returns list of trays to update (usefull only in ahnonay for now)
    def onTray(self, state):
        self.volatile = state
        return ((self.index, state),)

    #called on lock use, returns list of locks to update
    def onLock(self, state):
        #state is True when unlocked
        self.locked = not state
        return ((self.index, state),)

    @property
    def linkingRule(self):
        vault = ptVault()
        if vault.inMyPersonalAge():
            # may look useless, since we already have GUID, but this option also adds spawn point
            return PtLinkingRules.kOwnedBook
        else:
            return PtLinkingRules.kBasicLink

    def linkToAge(self, spawnPointTitle, spawnPointName):
        #let's just assume spawn point exists...
        sp = ptSpawnPointInfo(spawnPointTitle, spawnPointName)

        ageInfo = self.linkNode.getAgeInfo()

        if isinstance(ageInfo, ptVaultAgeInfoNode):
            ageInfo = ageInfo.asAgeInfoStruct()

        als = ptAgeLinkStruct()
        als.setAgeInfo(ageInfo)
        als.setSpawnPoint(sp)
        als.setLinkingRules(self.linkingRule)

        linkMgr = ptNetLinkingMgr()
        linkMgr.linkToAge(als)

class City(Book):
    # What's going on here:
    # City and connected instances (like spyroom) are picked from one of two possible sources:
    # child ages of Neighborhood (preferred) and Relto. Since hood child ages are shared,
    # link points are kept in player chronicle under name "CityBookLinks"
    # (to make things even more complicated, spawn points for public city are kept in
    # link node to AgeInfo in AgesIOwn, but we don't need those)
    # There is small problem connected with this: when visiting other players Relto,
    # you will see your own link points (or nothing, if dialog works that way).

    def __init__(self, index):
        Book.__init__(self, index, deletable = False)
        self.ageFilename = 'city'
        self.parentAgeInfo = None
        self.hoodLink = None

        #check if owner has city book
        ageSDL = PtGetAgeSDL()
        gotBook = ageSDL["psnlGotCityBook"][0]
        self.visible = gotBook
        self.childAges = None

        vault = ptVault()
        self.chronLocked = getAgeDataChronicle('CityBookLocked', True, canCreate = vault.inMyPersonalAge())

    # list of ages that are part of city
    ChildAgeNames = ["city", "BaronCityOffice", "Descent", "GreatZero", "spyroom", "Kveer"]

    # this list will be used, if existing spawn point was not found in child ages
    SpawnPoints = {"BaronCityOffice" : "BaronCityOffice",
                   "dsntShaftFall" : "Descent",
                   "grtzGrtZeroLinkRm" : "GreatZero",
                   "Spyroom" : "spyroom",
                   "Kveer" : "Kveer",
                   "islmGreatTree" : "city",
                   "islmDakotahRoof" : "city",
                   "islmPalaceBalcony03" : "city",
                   "islmPalaceBalcony02" : "city",
                }

    def updateChildAges(self):
        self.childAges = dict()

        # if we didn't set parent age (should be neighborhood instance)
        # or it's volatile, we will use current age info (i.e. Personal)
        if self.hoodLink is None or self.hoodLink.getVolatile():
            ageVault = ptAgeVault()
            self.parentAgeInfo = ageVault.getAgeInfo()
        else:
            self.parentAgeInfo = self.hoodLink.getAgeInfo()

        childAgesFolder = self.parentAgeInfo.getChildAgesFolder()
        contents = childAgesFolder.getChildNodeRefList()

        for content in contents:
            link = content.getChild()
            link = link.upcastToAgeLinkNode()
            if not link:
                continue

            info = link.getAgeInfo()
            ageName = info.getAgeFilename()
            if ageName in City.ChildAgeNames:
                self.childAges[ageName] = (link, info)


    def useHoodLink(self, ageLink):
        self.hoodLink = ageLink
        self.updateChildAges()

    @property
    def locked(self):
        if self.childAges is None:
            self.updateChildAges()

        if self.chronLocked is not None:
            return int(self.chronLocked.getValue())
        else:
            return True

    @locked.setter
    def locked(self, value):
        if self.childAges is None:
            self.updateChildAges()

        if self.chronLocked is None:
            PtDebugPrint("psnlBookshelf.City.locked: tried to change unexistent chronicle entry. Probable HAAAAAX!")
            return

        self.chronLocked.setValue(str(int(value)))

        for (link, _) in self.childAges.values():
            link.setLocked(value)
            link.save()

    @property
    def volatile(self):
        return False

    def linkToAge(self, spawnPointTitle, spawnPointName):
        self.updateChildAges() #do it, since hood volatileness might have changed

        vault = ptVault()
        inPersonal = vault.inMyPersonalAge()

        spawnPoint = None
        ageInfo = None

        #try to find existing spawn point
        for (link, info) in self.childAges.values():
            for sp in link.getSpawnPoints():
                if sp.getTitle() == spawnPointTitle and sp.getName() == spawnPointName:
                    spawnPoint = sp
                    ageInfo = info
                    break

            if spawnPoint is not None:
                break

        als = ptAgeLinkStruct()

        #in most cases we will have age guid, so basic link is ok
        als.setLinkingRules(PtLinkingRules.kBasicLink)

        # Can't find spawn point, try to use new
        if spawnPoint is None:
            PtDebugPrint("psnlBookshelf.City.linkToAge: Can't find spawn point (%s,%s), trying to create" % (spawnPointTitle, spawnPointName))
            try:
                ageName = City.SpawnPoints[spawnPointTitle]
                spawnPoint = ptSpawnPointInfo(spawnPointTitle, spawnPointName)
                try:
                    (_, ageInfo) = self.childAges[ageName]
                except KeyError:
                    if inPersonal:
                        #create new child age
                        ageInfo = ptAgeInfoStruct()
                        ageInfo.setAgeFilename(ageName)

                        parentAgeFilename = self.parentAgeInfo.getAgeFilename()
                        als.setParentAgeFilename(parentAgeFilename)
                        als.setLinkingRules(PtLinkingRules.kChildAgeBook)
                        PtDebugPrint("psnlBookshelf.City.linkToAge(): Creating child age %s, parent = %s" % (ageName, parentAgeFilename))
                    else:
                        # I think this is needed. When age doesn't exist and relto owner is member of hood
                        # different then ours, we have no way to create hood child age
                        # (ChildAgeBook can only create child ages for ages we own or for current age)
                        PtDebugPrint("psnlBookshelf.City.linkToAge(): Trying to link to non-existing age while visiting. Abort.")
                        return
            except KeyError:
                PtDebugPrint("psnlBookshelf.City.linkToAge(): Can't find anything about spawn point %s, aborting" % spawnPointTitle)
                return

        if isinstance(ageInfo, ptVaultAgeInfoNode):
            ageInfo = ageInfo.asAgeInfoStruct()

        ageInfo.setAgeInstanceName("Ae'gura")

        als.setAgeInfo(ageInfo)
        als.setSpawnPoint(spawnPoint)

        linkMgr = ptNetLinkingMgr()
        linkMgr.linkToAge(als)

class Ahnonay(Book):
    # What about this one?
    # For some strange reason, Ahnonay is not linked with normal AgeLink node,
    # but with chronicle entries in Relto folder AgeData.
    # This age is also connected with AhnonnayCathedral, so deleting
    # must be simultaneous (must be? anyway, that was in original file)

    #chronicle name -> instance variable name
    ChronicleEntries = {
                        "AhnonayVolatile" : "volatileChron",
                        "AhnonayLocked" : "lockedChron",
                        "AhnonayLink" : "ageGuidChron",
                      }


    def __init__(self, index):
        Book.__init__(self, index)
        self.ageFilename = "Ahnonay"

        self.cathedralBook = None


        self.lockedChron = None
        self.volatileChron = None
        self.ageGuidChron = None

        for chron in ageDataChronicles():
            try:
                chronName = chron.getName()
                varName = Ahnonay.ChronicleEntries[chronName]
                setattr(self, varName, chron)
                PtDebugPrint("psnlBookshelf.Ahnonay.__init__(): Found chron value %s" % chronName)
            except KeyError :
                pass

        self.visible = self.ageGuidChron is not None

    def addCathedralBook(self, book):
        if self.visible:
            self.cathedralBook = book
            book.ahnonayBook = self

    @property
    def locked(self):
        if self.lockedChron is not None:
            return int(self.lockedChron.getValue())
        else:
            return True

    @locked.setter
    def locked(self, value):
        if self.lockedChron is not None:
            self.lockedChron.setValue(str(int(value)))

    def setVolatileChron(self, value):
        if self.volatileChron is not None:
            self.volatileChron.setValue(str(int(value)))

    @property
    def volatile(self):
        if self.volatileChron is not None:
            return int(self.volatileChron.getValue())
        else:
            return False

    @volatile.setter
    def volatile(self, value):
        self.setVolatileChron(value)
        if self.cathedralBook is not None:
            #use original method to avoid recursive call
            Book.volatile.__set__(self.cathedralBook, value)

    def onTray(self, state):
        self.setVolatileChron(state)
        if self.cathedralBook is not None:
            return ((self.index, state), (self.cathedralBook.index, state))
        else:
            return ((self.index, state),)

    def linkToAge(self, spawnPointTitle, spawnPointName):
        sp = ptSpawnPointInfo(spawnPointTitle, spawnPointName)

        info = ptAgeInfoStruct()
        info.setAgeFilename(self.ageFilename)
        info.setAgeInstanceName(self.ageFilename)
        info.setAgeInstanceGuid(self.ageGuidChron.getValue())

        als = ptAgeLinkStruct()
        als.setAgeInfo(info)
        als.setSpawnPoint(sp)

        #basic link, since it's not in any of our folders
        als.setLinkingRules(PtLinkingRules.kBasicLink)

        linkMgr = ptNetLinkingMgr()
        linkMgr.linkToAge(als)

class AhnonayCathedral(Book):
    # Book should behave normally, unless it's connected with Ahnonay book

    def __init__(self, index):
        Book.__init__(self, index)
        self.ahnonayBook = None

    @property
    def volatile(self):
        if self.ahnonayBook:
            return self.ahnonayBook.volatile
        else:
            return Book.volatile.__get__(self)

    @volatile.setter
    def volatile(self, value):
        if self.ahnonayBook:
            self.ahnonayBook.setVolatileChron(value)

        Book.volatile.__set__(self, value)

    def onTray(self, state):
        self.volatile = state
        if self.ahnonayBook is not None:
            return ((self.index, state), (self.ahnonayBook.index, state))
        else:
            return ((self.index, state),)

class Neighborhood(Book):
    # different delete text, special linking rule

    deleteConfirmText = "Personal.Bookshelf.DeleteNeighborhoodBook"

    @property
    def linkingRule(self):

        vault = ptVault()
        if vault.inMyPersonalAge():
            return PtLinkingRules.kOwnedBook
        else:
            # If we are visiting and our own neighborhood book is volatile, this
            # option will replace link in our AgesIOwn folder.
            # Otherwise, it will just do basic link
            return PtLinkingRules.kOriginalBook

class Cleft(Book):
    # Special visiblity rules

    def __init__(self, index):
        Book.__init__(self, index, unlockable = False, deletable = False)
        ageSDL = PtGetAgeSDL()
        self.visible = ageSDL["CleftVisited"][0]

class PrivateBook(Book):
    #Can't delete, can't share

    def __init__(self, index):
        Book.__init__(self, index, unlockable = False, deletable = False)

specialBooks = {
                'city' : City,
                'Ahnonay' : Ahnonay,
                'AhnonayCathedral' : AhnonayCathedral,
                'Neighborhood' : Neighborhood,
                'Cleft' : Cleft,
                'Nexus' : PrivateBook,
                }

# this array defines which age books are on this shelf and where on the shelf they appear
# to add a book, replace an element with the name of the age, for instance: change None to BillsSuperCoolAge
# to change where a book appears on the shelf, change it's position in the array
linkLibrary = ["Neighborhood", "Nexus", "city", None, None, "Cleft", "Garrison", "Teledahn", "Kadish", "Gira", "Garden", "Negilahn", "Dereno", "Payiferen", "Tetsonot", "Ercana", "AhnonayCathedral", "Ahnonay",
               "Minkata", "Jalak", None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, "Myst"]

kBookCount = len(linkLibrary)

def respRun(key, receiver, fastForward, netPropagate):
    nt = ptNotify(key)
    nt.clearReceivers()
    nt.addReceiver(receiver)
    nt.netPropagate(netPropagate)
    nt.netForce(netPropagate)
    nt.setActivate(1.0)

    if fastForward:
        nt.setType(PtNotificationType.kResponderFF)

    nt.send()

class ItemState():

    def __init__(self, parentKey):
        self.activator = None
        self.onResp = None
        self.offResp = None
        self.state = False
        self.key = parentKey

    def toggleState(self, fastForward = False, netPropagate = True):
        if self.state:
            if self.offResp:
                respRun(self.key, self.offResp, fastForward, netPropagate)
        else:
            if self.onResp:
                respRun(self.key, self.onResp, fastForward, netPropagate)

        self.state = not self.state
        return self.state

    def setState(self, state, fastForward = False, netPropagate = True):
        if state != self.state:
            if state:
                if self.onResp:
                    respRun(self.key, self.onResp, fastForward, netPropagate)
            else:
                if self.offResp:
                    respRun(self.key, self.offResp, fastForward, netPropagate)

        self.state = state

class psnlBookshelf(ptModifier):
    def __init__(self):
        ptModifier.__init__(self)
        self.id = 5012

        self.version = 10
        PtDebugPrint("__init__psnlBookshelf v.%d" % self.version)

        self.animCount = 0
        self.showingBook = None

        self.bookshelfOperator = None
        self.amIOperator = False
        self.bookToDelete = None
        self.nameToIndex = dict()

    def IUpdateStateList(self, stateList, respList, attrName):
        for value in respList:
            parent = value.getParentKey()
            if parent:
                parentIndex = self.nameToIndex[parent.getName()]
                obj = stateList[parentIndex]
                setattr(obj, attrName, value)

                self.nameToIndex[value.getName()] = parentIndex

    def ICreateStateList(self, onResponder, offResponder, activator):
        result = [ItemState(self.key) for i in range(kBookCount)]
        self.IUpdateStateList(result, onResponder.value, 'onResp')
        self.IUpdateStateList(result, offResponder.value, 'offResp')
        self.IUpdateStateList(result, activator.value, 'activator')
        return result

    def OnFirstUpdate(self):
        self.nameToIndex = dict()
        for objList in (objLibrary.value, objLocks.value, objTrays.value):
            for (i, obj) in enumerate(objList):
                objName = obj.getName()
                self.nameToIndex[objName] = i

        self.traysState = self.ICreateStateList(respDeleteBook, respReturnTray, actTray)
        self.locksState = self.ICreateStateList(respOpenLock, respCloseLock, actLock)
        self.booksState = self.ICreateStateList(respPresentBook, respShelveBook, actBook)

        for tray in objTrays.value:
            tray.draw.disable()

    def OnServerInitComplete(self):
        ageSDL = PtGetAgeSDL()
        ageSDL.setNotify(self.key, "ShelfAUserID", 0.0)

        ageSDL.setFlags("ShelfABoolOperated", 1, 1)
        ageSDL.setFlags("ShelfAUserID", 1, 1)

        ageSDL.sendToClients("ShelfABoolOperated")
        ageSDL.sendToClients("ShelfAUserID")

        ageSDL.setFlags("CurrentPage", 1, 1)
        ageSDL.sendToClients("CurrentPage")

        self.bookshelfOperator = None

        #enable, let activator decide, if we can play
        actBookshelf.enable()

        if ageSDL["ShelfABoolOperated"][0]:
            self.IChangeShelfOperator(ageSDL["ShelfAUserID"][0])
        else:
            self.IClearShelfOperator()

        self.IUpdateBooks()

    def ITryLockBookshelfSDL(self, avatar):
        ageSDL = PtGetAgeSDL()
        avId = PtGetClientIDFromAvatarKey(avatar.getKey())

        #skip the boring part if we are alone
        if PtGetPlayerList():

            if self.bookshelfOperator:
                if self.bookshelfOperator == avId:
                    return True
                else:
                    PtDebugPrint("psnlBookshelf.ITryLockBookshelfSDL(): Failed, id %d is operating now" % self.bookshelfOperator)
                    return False

            operatorId = ageSDL["ShelfAUserID"][0]

            if  operatorId > 0 or ageSDL["ShelfABoolOperated"][0]:
                PtDebugPrint("psnlBookshelf.ITryLockBookshelfSDL(): Failed, id %d is operating now" % operatorId)
                return False

        ageSDL["ShelfABoolOperated"] = (1,)
        ageSDL["ShelfAUserID"] = (avId,)
        PtDebugPrint("psnlBookshelf.ITryLockBookshelfSDL(): Done. Bookshelf A user id = %d" % avId)
        return True


    def IUnlockBookshelfSDL(self):
        ageSDL = PtGetAgeSDL()
        ageSDL["ShelfABoolOperated"] = (0,)
        ageSDL["ShelfAUserID"] = (-1,)
        PtDebugPrint("psnlBookshelf.IResetBookshelfOperator:\twrote SDL - Bookshelf A has no user")

    def IChangeShelfOperator(self, operatorId):
        if operatorId <= 0:
            self.IClearShelfOperator()
            return

        if self.bookshelfOperator is not None and self.bookshelfOperator != operatorId:
            PtDebugPrint("psnlBookshelf.IOnLocalNotify(): local operator id = %s not equal to notify id = %s" %
                             (self.bookshelfOperator, operatorId))

        self.bookshelfOperator = operatorId

        if operatorId == PtGetLocalClientID():
            self.amIOperator = True
        else:
            self.amIOperator = False

    def IClearShelfOperator(self):
        actBookshelf.enable()
        self.bookshelfOperator = None
        self.amIOperator = False

    def OnSDLNotify(self, varName, SDLname, playerID, tag):
        if varName in  ("ShelfABoolOperated", "ShelfAUserID"):
            ageSDL = PtGetAgeSDL()
            if ageSDL["ShelfAUserID"][0] > 0 or ageSDL["ShelfABoolOperated"][0]:
                self.IChangeShelfOperator(ageSDL["ShelfAUserID"][0])
            else:
                self.IClearShelfOperator()


    def IFindEventByType(self, events, eventType):
        for event in events:
            if event[0] == eventType:
                return event
        PtDebugPrint("psnlBookshelf.IFindEventByType: event type %d not found" % eventType)
        return None

    def IOnActBookshelf(self, state, events):
        avatar = PtFindAvatar(events)

        if PtFindAvatar(events) != avatar or not PtWasLocallyNotified(self.key):
            return

        event = self.IFindEventByType(events, kPickedEvent)

        if event is not None and event[1]: #entry event
            if (avatar != PtGetLocalAvatar() or
                not PtWasLocallyNotified(self.key)):
                PtDebugPrint("psnlBookshelf.IOnActBookshelf(): Notify not for us!")

            avId = PtGetClientIDFromAvatarKey(avatar.getKey())

            if not self.ITryLockBookshelfSDL(avatar):
                PtDebugPrint("psnlBookshelf.IOnActBookshelf(): It's rude to interrupt preople! Go away!")
                return

            avId = PtGetClientIDFromAvatarKey(avatar.getKey())

            self.INotifyBookshelfBusy()
            self.IChangeShelfOperator(avId)
            respRaiseShelfClickable.run(self.key, netPropagate = 0)

            # Disable First Person Camera
            cam = ptCamera()
            cam.undoFirstPerson()
            cam.disableFirstPersonOverride()
            PtRecenterCamera()
            seekBehavior.run(avatar)

            self.animCount = 0

    def IOnSeekBahaviour(self, state, events):
        event = self.IFindEventByType(events, kMultiStageEvent)

        if event[1] == 0: # Smart seek completed. Exit multistage, and show GUI.
            avatar = PtFindAvatar(events)
            seekBehavior.gotoStage(avatar, -1)
            PtDebugPrint("psnlBookshelf.OnNotify():\tengaging bookshelf")

            avatar.draw.disable()

            virtCam = ptCamera()
            virtCam.save(shelfCamera.sceneobject.getKey())

            PtSendKIMessage(PlasmaKITypes.kDisableKIandBB, 0)

            PtEnableControlKeyEvents(self.key)
            actBookshelf.disable()
            actBookshelfExit.enable()

    def IDisengageShelf(self):
        PtDebugPrint ("psnlBookshelf.IDisengageShelf: Player %s is done with the bookshelf." % (self.bookshelfOperator))

        if self.showingBook is not None:
            bookObj = self.booksState[self.showingBook]
            bookObj.setState(False) #start book hide

        self.IUnlockBookshelfSDL()
        self.INotifyBookshelfBusy(False)
        self.IClearShelfOperator()

        respLowerShelfClickable.run(self.key)

        avatar = PtGetLocalAvatar()
        avatar.draw.enable()

        cam = ptCamera()
        cam.enableFirstPersonOverride()
        # go back to the Hut Circle Cam
        virtCam = ptCamera()
        virtCam.save(HutCamera.sceneobject.getKey())
        PtEnableMovementKeys()
        actBookshelfExit.disable()
        actBookshelf.enable()
        PtDisableControlKeyEvents(self.key)
        PtSendKIMessage(PlasmaKITypes.kEnableKIandBB, 0)

    def IOnActBookshelfExit(self, state, events):
        self.IDisengageShelf()

    def IOnLocalNotify(self, state, events):
        event = self.IFindEventByType(events, kVariableEvent)
        if event[1] == 'BookShelfBusy':
            #somebody is leaving bookshelf
            if not events[0][3]:
                self.IClearShelfOperator()
        elif self.amIOperator and event[1] == "YesNo" and event[3] == 1:
            self.IChangeBookVolatileness(self.bookToDelete, True)

    def IOnActBook(self, state, events):
        event = self.IFindEventByType(events, kPickedEvent)
        objPicked = event[3]
        objName = objPicked.getName()
        index = self.nameToIndex[objName]

        book = self.books[index]
        if book is None:
            PtDebugPrint("psnlBookshelf.IOnActBook(): chosen book is empty")
            return

        if book.locked:
            #need to unlock first
            self.locksState[index].setState(True)
        else:
            #go straight to presenting
            self.booksState[index].setState(True)

        self.animCount += 1

        self.showingBook = index

    def IOnActLock(self, state, events):
        event = self.IFindEventByType(events, kPickedEvent)
        objPicked = event[3]
        objName = objPicked.getName()
        index = self.nameToIndex[objName]
        state = self.locksState[index].state

        book = self.books[index]
        PtDebugAssert(book is not None, "Tried to lock empty book at index %d " % index)

        for (bookIndex, newState) in book.onLock(not state):
            self.locksState[bookIndex].setState(newState)
            self.animCount += 1

    def IOnActTray(self, state, events):
        event = self.IFindEventByType(events, kPickedEvent)
        objPicked = event[3]
        objName = objPicked.getName()
        index = self.nameToIndex[objName]
        state = self.traysState[index].state

        book = self.books[index]
        PtDebugAssert(book is not None, "Tried to delete empty book at index %d " % index)

        #book already volatile, undelete
        if book.volatile:
            self.IChangeBookVolatileness(book, False)
        else:
            self.bookToDelete = book
            PtYesNoDialog(self.key, PtGetLocalizedString(book.deleteConfirmText))

    def IDefaultRespHandler(self, name):
        def handler(state, events):
            self.animCount -= 1
            PtDebugPrint("psnlBookshelf: default response from %s, anim count = %d" % (name, self.animCount))
        return handler

    def IOnRespOpenLock(self, state, events):
        #are we going to show book after that?
        if self.showingBook is not None:
            self.booksState[self.showingBook].setState(True)
        else:
            #no, just unlock. Finish animation
            self.animCount -= 1

    def IOnRespPresentBook(self, state, events):
        if self.showingBook is None:
            PtDebugPrint("psnlBookshelf.IOnRespPresentBook(): got here with no book chosen")
        else:
            self.IStartBookDialog(self.showingBook)

    def IOnActLinkingBookGUIPopup(self, state, events):
        if self.showingBook is None:
            PtDebugPrint("psnlBookshelf.IOnActLinkingBookGUIPopup(): got here with no book chosen")
            return

        event = self.IFindEventByType(events, kVariableEvent)
        command = event[1].split(",")

        if command[0] == "IShelveBook":
            pass #nothing special to do
        elif command[0] == "ILink":
            self.IDisengageShelf()
            book = self.books[self.showingBook]
            book.linkToAge(spawnPointName = command[1], spawnPointTitle = command[2])

        self.booksState[self.showingBook].setState(False) #hide the book

    def IOnRespShelveBook(self, state, events):
        if self.showingBook is not None:
            book = self.books[self.showingBook]
            if book is None:
                PtDebugPrint("psnlBookshelf.IOnRespPresentBook(): chosen book is empty")
                return

            #if book is locked, we need to update lock
            if book.locked:
                self.locksState[self.showingBook].setState(False)
            else:
                self.animCount -= 1

            #we don't need this anymore
            self.showingBook = None


    def OnNotify(self, state, id, events):
        if not hasattr(self, 'onNotifyActions'):
            self.onNotifyActions = {
             actBookshelf.id : (self.IOnActBookshelf, False, False),
             seekBehavior.id: (self.IOnSeekBahaviour, True, False),
             actBookshelfExit.id: (self.IOnActBookshelfExit, True, True),

             - 1: (self.IOnLocalNotify, False, False),

             actLinkingBookGUIPopup.id: (self.IOnActLinkingBookGUIPopup, True, False),

             actBook.id : (self.IOnActBook, True, True),
             respPresentBook.id : (self.IOnRespPresentBook, True, False),
             respShelveBook.id : (self.IOnRespShelveBook, True, False),

             actLock.id : (self.IOnActLock, True, True),
             respOpenLock.id : (self.IOnRespOpenLock, True, False),
             respCloseLock.id : (self.IDefaultRespHandler("OnRespCloseLock"), True, False),

             actTray.id : (self.IOnActTray, True, True),
             respReturnTray.id : (self.IDefaultRespHandler("OnRespReturnTray"), True, False),
             respDeleteBook.id : (self.IDefaultRespHandler("OnRespDeleteBook"), True, False),
            }

        try:
            (action, needOperator, needAnimFinished) = self.onNotifyActions[id]

            if action is not None:
                if not ((needOperator and not self.amIOperator) or
                        (needAnimFinished and self.animCount > 0)):
                    action(state, events)
        except KeyError:
            pass

    def IChangeBookVolatileness(self, book, state):
        for (bookIndex, newState) in book.onTray(state):
            # play animation
            self.traysState[bookIndex].setState(newState)

            if newState:
                self.locksState[bookIndex].activator.disable()
            else:
                self.locksState[bookIndex].activator.enable()

            self.animCount += 1

            tmpBook = self.books[bookIndex]

            if tmpBook is None:
                PtDebugPrint("psnlBookshelf.IChangeBookVolatileness(): tried to delete empty book. Ooops")
                return

            if newState:
                contents = "Volatile" + tmpBook.ageFilename
            else:
                contents = "NotVolatile" + tmpBook.ageFilename

            note = ptNotify(self.key)
            note.setActivate(1.0)
            note.addVarNumber(contents, 1)
            note.send()

    def INotifyBookshelfBusy(self, busy = True):
        notify = ptNotify(self.key)
        notify.clearReceivers()
        notify.addReceiver(self.key)
        notify.netPropagate(1)
        notify.netForce(1)
        notify.setActivate(1.0)
        notify.addVarNumber('BookShelfBusy', float(busy))
        notify.send()

    def IStartBookDialog(self, index):
        book = self.books[index]

        if book is None:
            PtDebugPrint("psnlBookshelf.IStartBookDialog(): chosen book is empty")
            return

        note = ptNotify(self.key)
        note.setActivate(1.0)
        note.addVarNumber("%s,%d" % (book.ageFilename, index), PtGetLocalClientID())
        note.send()

    def OnControlKeyEvent(self, controlKey, activeFlag):
        if (not self.animCount and
            controlKey in (PlasmaControlKeys.kKeyExitMode, PlasmaControlKeys.kKeyMoveBackward,
                           PlasmaControlKeys.kKeyRotateLeft, PlasmaControlKeys.kKeyRotateRight)):
            self.IDisengageShelf()

    def IAddAndUpdateBook(self, bookData, isMyAge):
        if not bookData.visible:
            return

        index = bookData.index
        self.books[index] = bookData

        tray = self.traysState[index]
        lock = self.locksState[index]
        book = self.booksState[index]

        lock.setState(not bookData.locked, fastForward = True, netPropagate = False)
        tray.setState(bookData.volatile, fastForward = True, netPropagate = False)

        if isMyAge:
            if bookData.unlockable:
                lock.activator.enable()

            if bookData.deletable:
                tray.activator.enable()

        if not bookData.volatile:
            if isMyAge or not bookData.locked:
                book.activator.enable()

    def IGetBookForAge(self, ageName):
        try:
            index = linkLibrary.index(ageName)
        except ValueError:
            return None

        bookClass = specialBooks.get(ageName, Book)
        return bookClass(index) #create book instance


    def IUpdateBooks(self):
        actTray.disable()
        actBook.disable()
        actLock.disable()

        self.books = [None] * kBookCount

        vault = ptVault()
        isMyAge = vault.inMyPersonalAge()

        ageVault = ptAgeVault()

        linksFolder = ageVault.getBookshelfFolder()
        contents = linksFolder.getChildNodeRefList()

        #handle extra weird Ahnonay (since it has no link entry, only chronicle values)
        ahnonayBook = self.IGetBookForAge('Ahnonay')

        #handle not-so-weird city (one book - many ages)
        cityBook = self.IGetBookForAge('city')

        #handle normal and slightly weird books
        for content in contents:
            link = content.getChild()
            link = link.upcastToAgeLinkNode()
            info = link.getAgeInfo()

            ageName = info.getAgeFilename()

            # Just to be safe. In typical case only 'city' instance can be in AgesIOwn folder
            if ageName in City.ChildAgeNames:
                continue

            book = self.IGetBookForAge(ageName)

            if book is None:
                continue

            #special case for synchronized deleting
            if ageName == 'AhnonayCathedral':
                ahnonayBook.addCathedralBook(book)

            #special case for city ages (which are either hood child ages or relto child ages) 
            elif ageName == 'Neighborhood':
                cityBook.useHoodLink(link)

            book.setLinkNode(link)
            self.IAddAndUpdateBook(book, isMyAge)

        self.IAddAndUpdateBook(ahnonayBook, isMyAge)
        self.IAddAndUpdateBook(cityBook, isMyAge)

        #hide empty books
        for (index, book) in enumerate(self.books):
            if book is None:
                objLibrary.value[index].draw.disable()
