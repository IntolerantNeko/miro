; These are passed in from setup.py:
;  CONFIG_VERSION        eg, "0.8.0"
;  CONFIG_PROJECT_URL    eg, "http://www.participatoryculture.org/"
;  CONFIG_SHORT_APP_NAME eg, "Democracy"
;  CONFIG_LONG_APP_NAME  eg, "Democracy Player"
;  CONFIG_PUBLISHER      eg, "Participatory Culture Foundation"
;  CONFIG_EXECUTABLE     eg, "Democracy.exe"
;  CONFIG_ICON           eg, "Democracy.ico"
;  CONFIG_OUTPUT_FILE    eg, "Democracy-0.8.0.exe"

!define INST_KEY "Software\${CONFIG_PUBLISHER}\${CONFIG_LONG_APP_NAME}"
!define UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${CONFIG_LONG_APP_NAME}"

!define RUN_SHORTCUT "${CONFIG_LONG_APP_NAME}.lnk"
!define UNINSTALL_SHORTCUT "Uninstall ${CONFIG_SHORT_APP_NAME}.lnk"

Name "${CONFIG_LONG_APP_NAME} ${CONFIG_VERSION}"
OutFile ${CONFIG_OUTPUT_FILE}
InstallDir "$PROGRAMFILES\${CONFIG_PUBLISHER}\${CONFIG_LONG_APP_NAME}"
InstallDirRegKey HKLM "${INST_KEY}" "Install_Dir"
SetCompressor lzma

SetOverwrite ifnewer
CRCCheck on

Icon ${CONFIG_ICON}

Var STARTMENU_FOLDER

!include "MUI.nsh"
!include "Sections.nsh"

;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
;; Pages                                                                     ;;
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

; Welcome page
!define MUI_WELCOMEPAGE_TITLE_3LINES
!insertmacro MUI_PAGE_WELCOME

; License page
!insertmacro MUI_PAGE_LICENSE "license.txt"

; Component selection page
!define MUI_COMPONENTSPAGE_TEXT_COMPLIST \
  "Please choose which optional components to install."
!insertmacro MUI_PAGE_COMPONENTS

; Installation directory selection page
!insertmacro MUI_PAGE_DIRECTORY

; Start menu folder name selection page
!define MUI_STARTMENUPAGE_DEFAULTFOLDER "${CONFIG_LONG_APP_NAME}"
!insertmacro MUI_PAGE_STARTMENU Application $STARTMENU_FOLDER

; Installation page
!insertmacro MUI_PAGE_INSTFILES

; Finish page
!define MUI_FINISHPAGE_RUN "$INSTDIR\${CONFIG_EXECUTABLE}"
!define MUI_FINISHPAGE_LINK \
  "Click here to visit the ${CONFIG_PUBLISHER} homepage."
!define MUI_FINISHPAGE_LINK_LOCATION "${CONFIG_PROJECT_URL}"
!define MUI_FINISHPAGE_NOREBOOTSUPPORT
!insertmacro MUI_PAGE_FINISH

; Uninstaller pages
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
;; Languages                                                                 ;;
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

!insertmacro MUI_LANGUAGE "English" # first language is the default language
!insertmacro MUI_LANGUAGE "French"
!insertmacro MUI_LANGUAGE "German"
!insertmacro MUI_LANGUAGE "Spanish"
!insertmacro MUI_LANGUAGE "SimpChinese"
!insertmacro MUI_LANGUAGE "TradChinese"
!insertmacro MUI_LANGUAGE "Japanese"
!insertmacro MUI_LANGUAGE "Korean"
!insertmacro MUI_LANGUAGE "Italian"
!insertmacro MUI_LANGUAGE "Dutch"
!insertmacro MUI_LANGUAGE "Danish"
!insertmacro MUI_LANGUAGE "Swedish"
!insertmacro MUI_LANGUAGE "Norwegian"
!insertmacro MUI_LANGUAGE "Finnish"
!insertmacro MUI_LANGUAGE "Greek"
!insertmacro MUI_LANGUAGE "Russian"
!insertmacro MUI_LANGUAGE "Portuguese"
!insertmacro MUI_LANGUAGE "Arabic"

;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
;; Reserve files (interacts with solid compression to speed up installation) ;;
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

!insertmacro MUI_RESERVEFILE_LANGDLL
!insertmacro MUI_RESERVEFILE_INSTALLOPTIONS

;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
;; Macros
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

!macro checkUnhandledExtension ext sectionName
  Push $0
  ReadRegStr $0 HKCR "${ext}" ""
  StrCmp $0 "" +2
  StrCmp $0 "DemocracyPlayer" 0 +3
    SectionGetFlags ${sectionName} $0
    IntOp $0 $0 | 1
    SectionSetFlags ${sectionName} $0
  Pop $0
!macroend

;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
;; Sections                                                                  ;;
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

Section "-${CONFIG_LONG_APP_NAME}"

; Warn users of Windows 9x/ME that they're not supported
  Push $R0
  ClearErrors
  ReadRegStr $R0 HKLM \
    "SOFTWARE\Microsoft\Windows NT\CurrentVersion" CurrentVersion
  IfErrors 0 lbl_winnt
  MessageBox MB_ICONEXCLAMATION \
     "WARNING: Democracy Player is not officially supported on this version of Windows$\r$\n$\r$\nVideo playback is known to be broken, and there may be other problems"
lbl_winnt:

  Pop $R0
  ; Remove anything already in the installation dir if it exists
  RMDir /r $INSTDIR

  SetShellVarContext all
  SetOutPath "$INSTDIR"

  File  ${CONFIG_EXECUTABLE}
  File  ${CONFIG_ICON}
  File  Democracy_Downloader.exe
  File  application.ini
  File  msvcp71.dll  
  File  msvcr71.dll  
  File  python24.dll
  File  boost_python-vc71-mt-1_33.dll

  File  /r chrome
  File  /r components
  File  /r defaults
  File  /r resources
  File  /r vlc-plugins
  File  /r xulrunner

  ; Create a ProgID for Democracy
  WriteRegStr HKCR "DemocracyPlayer" "" "Democracy Player"
  WriteRegStr HKCR "DemocracyPlayer\shell" "" "open"
  WriteRegStr HKCR "DemocracyPlayer\DefaultIcon" "" "$INSTDIR\Democracy.exe,0"
  WriteRegStr HKCR "DemocracyPlayer\shell\open\command" "" \
    '$INSTDIR\Democracy.exe "%1"'
  WriteRegStr HKCR "DemocracyPlayer\shell\edit" "" "Edit Options File"
  WriteRegStr HKCR "DemocracyPlayer\shell\edit\command" "" \
    '$INSTDIR\Democracy.exe "%1"'

  ; Democracy complains if this isn't present and it can't create it
  CreateDirectory "$INSTDIR\xulrunner\extensions"

  !insertmacro MUI_STARTMENU_WRITE_BEGIN Application
  CreateDirectory "$SMPROGRAMS\$STARTMENU_FOLDER"
  CreateShortCut "$SMPROGRAMS\$STARTMENU_FOLDER\${RUN_SHORTCUT}" \
    "$INSTDIR\${CONFIG_EXECUTABLE}" "" "$INSTDIR\${CONFIG_ICON}"
  CreateShortCut "$SMPROGRAMS\$STARTMENU_FOLDER\${UNINSTALL_SHORTCUT}" \
    "$INSTDIR\uninstall.exe"
  !insertmacro MUI_STARTMENU_WRITE_END
SectionEnd

Section "Desktop icon" SecDesktop
  CreateShortcut "$DESKTOP\${RUN_SHORTCUT}" "$INSTDIR\${CONFIG_EXECUTABLE}" \
    "" "$INSTDIR\${CONFIG_ICON}"
SectionEnd

Section /o "Handle .torrent files" SecRegisterTorrent
  WriteRegStr HKCR ".torrent" "" "DemocracyPlayer"
SectionEnd

Section /o "Handle .avi files" SecRegisterAvi
  WriteRegStr HKCR ".avi" "" "DemocracyPlayer"
SectionEnd

Section /o "Handle .mpg files" SecRegisterMpg
  WriteRegStr HKCR ".mpg" "" "DemocracyPlayer"
SectionEnd

Section /o "Handle .mov files" SecRegisterMov
  WriteRegStr HKCR ".mov" "" "DemocracyPlayer"
SectionEnd

Section /o "Handle .wmv files" SecRegisterWmv
  WriteRegStr HKCR ".wmv" "" "DemocracyPlayer"
SectionEnd

Section -NotifyShellExentionChange
  System::Call 'Shell32::SHChangeNotify(i 0x8000000, i 0, i 0, i 0)'
SectionEnd

Function .onInit
  ; Is the app already installed? Bail if so.
  ReadRegStr $R0 HKLM "${INST_KEY}" "InstallDir"
  StrCmp $R0 "" done
 
  ; Should we uninstall the old one?
  MessageBox MB_OKCANCEL|MB_ICONEXCLAMATION \
  "It looks like you already have a copy of ${CONFIG_LONG_APP_NAME} $\n\
installed.  Do you want to continue and overwrite it?" \
       IDOK continue
  Quit
  continue:
  RMDir /r $R0 ; Remove the old installation

  done:
  !insertmacro MUI_LANGDLL_DISPLAY

  ; Make check boxes for unhandled file extensions.
  !insertmacro checkUnhandledExtension ".torrent" ${SecRegisterTorrent}
  !insertmacro checkUnhandledExtension ".avi" ${SecRegisterAvi}
  !insertmacro checkUnhandledExtension ".mpg" ${SecRegisterMpg}
  !insertmacro checkUnhandledExtension ".mov" ${SecRegisterMov}
  !insertmacro checkUnhandledExtension ".wmv" ${SecRegisterWmv}
FunctionEnd

Section -Post
  WriteUninstaller "$INSTDIR\uninstall.exe"
  WriteRegStr HKLM "${INST_KEY}" "InstallDir" $INSTDIR
  WriteRegStr HKLM "${INST_KEY}" "Version" "${CONFIG_VERSION}"
  WriteRegStr HKLM "${INST_KEY}" "" "$INSTDIR\${CONFIG_EXECUTABLE}"

  WriteRegStr HKLM "${UNINST_KEY}" "DisplayName" "$(^Name)"
  WriteRegStr HKLM "${UNINST_KEY}" "UninstallString" "$INSTDIR\uninstall.exe"
  WriteRegStr HKLM "${UNINST_KEY}" "DisplayIcon" "$INSTDIR\${CONFIG_EXECUTABLE}"
  WriteRegStr HKLM "${UNINST_KEY}" "DisplayVersion" "${CONFIG_VERSION}"
  WriteRegStr HKLM "${UNINST_KEY}" "URLInfoAbout" "${CONFIG_PROJECT_URL}"
  WriteRegStr HKLM "${UNINST_KEY}" "Publisher" "${CONFIG_PUBLISHER}"
SectionEnd

Section "Uninstall" SEC91
  SetShellVarContext all

  ; Remove the program
  RMDir /r $INSTDIR

  ; Remove Start Menu shortcuts
  !insertmacro MUI_STARTMENU_GETFOLDER Application $R0
  Delete "$SMPROGRAMS\$R0\${RUN_SHORTCUT}"
  Delete "$SMPROGRAMS\$R0\${UNINSTALL_SHORTCUT}"
  RMDir "$SMPROGRAMS\$R0"

  ; Remove desktop shortcut
  Delete "$DESKTOP\${RUN_SHORTCUT}"

  ; Remove registry keys
  DeleteRegKey HKLM "${INST_KEY}"
  DeleteRegKey HKLM "${UNINST_KEY}"
  DeleteRegValue HKLM "Software\Microsoft\Windows\CurrentVersion\Run" "Democracy Player"

  SetAutoClose true
SectionEnd
