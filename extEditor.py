# Copyright (C) 2015  Arthur Yidi
# License: BSD Simplified
"""

Houdini External Editor
Launcher & Configuration

Script is executed by the Menu options:
- Edit w/ External Editor
- Configure External Editor

"""
import os
import sys
import subprocess
import tempfile
import shlex
from bisect import bisect_left
import hutil.enum
import argparse

OS = sys.platform.lower()

def editParmExternal(editor, parm):
    """
    Provides the ability to quickly edit a parameter using an external editor.
    """
    editorargs = shlex.split(editor)
    keyframes = parm.keyframes()
    keyframe = None
    parmType = parm.parmTemplate().type()
    parmEditorLang = parm.parmTemplate().tags().get('editorlang', '').lower()
    parmIsNum = (parmType == hou.parmTemplateType.Int) or (parmType == hou.parmTemplateType.Float)
    parmIsExpression = len(keyframes)
    parmValue = ''

    if parmIsExpression:
        # find the appropriate keyframe
        curFrame = hou.frame()
        frames = [k.frame() for k in keyframes]
        i = bisect_left(frames, curFrame)
        if not hou.almostEqual(curFrame, frames[min(i,len(frames)-1)]):
            i = max(0, i - 1)
        keyframe = keyframes[i]
        parmValue = keyframe.expression()
    else:
        parmValue = parm.evalAsString()

    # set the suffix
    defaultLang = parm.node().expressionLanguage() 
    if parmIsExpression:
        defaultLang = keyframe.expressionLanguage()
    suff = '.cmd'
    pref = '%s_%s__' % (parm.node().name(), parm.name())

    if parmType == hou.parmTemplateType.String:
        if 'vex' in parmEditorLang:
            suff = '.vfl'
        elif 'python' in parmEditorLang:
            suff = '.py'
    elif defaultLang == hou.exprLanguage.Python:
        suff = '.py'

    with tempfile.NamedTemporaryFile(prefix=pref, suffix=suff) as f:
        f.write(parmValue)
        f.flush()
        os.fsync(f.fileno())

        hou.ui.setStatusMessage(
            '  Close external editor window or '
            'application to return to Houdini.',
            severity=hou.severityType.ImportantMessage)

        editorargs.append(f.name)
        status = error = 1
        try:
            status = subprocess.call(editorargs)
        except OSError as e:
            error = e

        if status != 0:
            options = hou.ui.displayMessage(
                'External editor was not found.\n',
                help='Change editor configuration and try again.\n\n',
                details=str('\n'.join(editorargs)) + '\n\n' + str(error),
                buttons=('Configure', 'Cancel'),
                close_choice=1,
                severity=hou.severityType.Error)

            if options == 0:
                editor = configExternalEditor()
                if editor is not None:
                    editParmExternal(editor, parm)
            return

        hou.ui.setStatusMessage('')

        with open(f.name) as result:
            lines = result.readlines()
            hasLines = len(lines)

            if hasLines:
                lines[-1] = lines[-1].rstrip()
                newParmValue = ''.join(lines)
                if parmIsExpression:
                    keyframe.setExpression(newParmValue)
                else:
                    if hasLines > 1:
                        if parmType == hou.parmTemplateType.String:
                            parm.set(newParmValue)
                        else:
                            parm.setExpression(newParmValue)
                    else:
                        if parmIsNum:
                            try:
                                newParmValue = float(newParmValue)
                            except ValueError:
                                parm.setExpression(newParmValue)
                            else:
                                if parmType == hou.parmTemplateType.Int:
                                    newParmValue = int(newParmValue)
                                parm.set(newParmValue)
                        else:
                            try:
                                parm.set(newParmValue)
                            except (hou.OperationFailed, TypeError) as e:
                                hou.ui.displayMessage(
                                    'Unable to edit parameter.\n',
                                    details=str(e),
                                    severity=hou.severityType.Error)
            else:
                if parmIsExpression:
                    # houdini mode: keyframe.setExpression('')
                    # preferred mode: delete keyframe
                    if len(keyframes) > 1:
                        hou.hscript(' '.join(['chkeyrm',
                                              parm.path(),
                                              str(keyframe.frame())]))
                    else:
                        parm.deleteAllKeyframes()
                    keyframe = None
                else:
                    parm.revertToDefaults()

            # update keyframe
            if keyframe:
                parm.setKeyframe(keyframe)


def configExternalEditor():
    """
    Help configure external editor using houdini.env

    Sets the VISUAL = "" environment variable.
    """
    editorsList = {
        'mac' : [
            {
                'name' : 'Sublime 3',
                'search' : 'com.sublimetext.3',
                'command' : '"{}/Contents/SharedSupport/bin/subl" -w'
            },
            {
                'name' : 'Sublime 2',
                'search' : 'com.sublimetext.2',
                'command' : '"{}/Contents/SharedSupport/bin/subl" -w'
            },
            {
                'name' : 'MacVim',
                'search' : 'org.vim.MacVim',
                'command' : '"{}/Contents/MacOS/Vim" -gfn'
            },
            {
                'name' : 'TextWrangler',
                'search' : 'com.barebones.textwrangler',
                'command' : '"{}/Contents/Helpers/edit" -w'
            },
            {
                'name' : 'BBEdit',
                'search' : 'com.barebones.bbedit',
                'command' : '"{}/Contents/Helpers/bbedit_tool" -w'
            },
            {
                'name' : 'TextMate',
                'search' : 'com.macromates.TextMate.preview',
                'command' : '"{}/Contents/Resources/mate" -w'
            },
            {
                'name' : 'Emacs',
                'search' : 'org.gnu.Emacs',
                'command' : '"{}/Contents/MacOS/Emacs"'
            },
            {
                'name' : 'Atom',
                'search' : 'com.github.atom',
                'command' : '"{}/Contents/MacOS/Atom" -fw'
            },
            {
                'name' : 'Xcode',
                'search' : 'com.apple.dt.Xcode',
                'command' : '"{}/Contents/MacOS/Xcode"'
            }
        ],
        'linux' : [
            {
                'name' : 'Sublime',
                'search' : ['subl', 'sublime-text', 'sublime_text', 'sublime'],
                'command' : '"{}" -w'
            },
            {
                'name' : 'Vim',
                'search' : ['gvim', 'vim'],
                'command' : '"{}" -gfn'
            },
            {
                'name' : 'gedit',
                'search' : ['gedit'],
                'command' : '"{}" -w'
            },
            {
                'name' : 'kate',
                'search' : ['kate'],
                'command' : '"{}" -u'
            },
            {
                'name' : 'KWrite',
                'search' : ['kwrite'],
                'command' : '"{}"'
            },
            {
                'name' : 'Emacs',
                'search' : ['emacs'],
                'command' : '"{}"'
            }
        ],
        'win' : [
            {
                'name' : 'Sublime 3',
                'search' : r'SOFTWARE\Microsoft\Windows\CurrentVersion\App',
                'command' : r'"{}" -w'
            },
            {
                'name' : 'Sublime 2',
                'search' : r'SOFTWARE\Microsoft\Windows\CurrentVersion\App',
                'command' : r'"{}" -w'
            },
            {
                'name' : 'Notepad++',
                'search' : r'SOFTWARE\Microsoft\Windows\CurrentVersion\App',
                'command' : r'"{}" -nosession -notabbar'
            },
            {
                'name' : 'Vim',
                'search' : r'',
                'command' : r'"{}" -gfn'
            },
            {
                'name' : 'Emacs',
                'search' : r'',
                'command' : r'"{}" -w'
            }
        ]
    }

    installedEditors = []
    editors = []

    # find installed editors
    if 'darwin' in OS:
        editors = editorsList['mac']
        args = ['mdfind', 'kMDItemCFBundleIdentifier', '=', '']

        for i in range(len(editors)):
            editor = editors[i]
            args[3] = editor['search'] 
            try:
                out = subprocess.check_output(args)
            except (OSError, subprocess.CalledProcessError):
                pass
            else:
                out = out.split('\n')[0].strip()
                if out:
                    editor['command'] = editor['command'].format(out)
                    installedEditors.append(i)

    elif 'linux' in OS:
        editors = editorsList['linux']

        # in python 3 use shutil.which 
        from distutils.spawn import find_executable

        for i in range(len(editors)):
            editor = editors[i]
            for exe in editor['search']:
                exePath = find_executable(exe)
                if exePath:
                    editor['command'] = editor['command'].format(exePath)
                    installedEditors.append(i)
                    break

    else:
        editors = editorsList['win']
        # TODO implement me
        pass

    selectedEditor = None
    manualEditSelected = False
    editor = hou.getenv('VISUAL') or hou.getenv('EDITOR') or ''

    if len(installedEditors):
        editorChoices = []
        for i in range(len(installedEditors)):
            editorNum = installedEditors[i]
            editorChoices.append("%d) %s" % (i+1, editors[editorNum]['name']))
        editorChoices.append('-' * 60)
        if editor:
            editorChoices.append('- Edit Current Setting')
        else:
            editorChoices.append('- Other')

        # select from list or apply, edit, cancel
        selectedEditor = hou.ui.selectFromList(
            editorChoices,
            default_choices=(-1,),
            message='Select Editor:\n',
            title='Configure External Editor',
            exclusive=True)

        if not len(selectedEditor):
            return None
        
        selectedEditor = selectedEditor[0]
        if selectedEditor > len(installedEditors) - 1:
            manualEditSelected = True
        else:
            editor = editors[installedEditors[selectedEditor]]['command']

    example = '"/Applications/External Editor/exec" -arg'
    if OS.startswith('win'):
        example = '"C:\Program Files\External Editor\editor.exe" -arg' 

    if manualEditSelected or not len(installedEditors):
        (option, visualPath) = hou.ui.readMultiInput(
            'Edit path and arguments for external editor.\n',
            ['VISUAL'],
            help='Surround path with quotes if it contains spaces.\n\n'
                 'Example:\n%s'
                 '%s\n' % (example, (' ' * 90)),
            buttons=('Save', 'Cancel'),
            initial_contents=[str(editor)])
      
        if option == 1:
            return None

        editor = visualPath[0].strip()

    # houdini crashes if passed a string with unicode
    try:
        editor.decode('ascii')
    except UnicodeDecodeError:
        hou.ui.displayMessage(
            'Non-Latin characters in path detected.\n',
            help='Houdini only supports ASCII characters in path.\n',
            details=editor,
            severity=hou.severityType.Error)
        return None
    else:
        hou.putenv('VISUAL', editor)

    houdiniEnv = os.path.join(hou.homeHoudiniDirectory(), 'houdini.env')

    # save setting to houdini.env
    try:
        f = open(houdiniEnv, 'r+')
    except IOError as e:
        hou.ui.displayMessage(
            'External editor setting was not saved.\n',
            help='Unable to open environment settings.\n',
            details=str(e),
            severity=hou.severityType.Error)
    else:
        with f:
            removeSetting = not editor
            insert = 'VISUAL = "%s"\n' % editor if not removeSetting else ''
            settingUpdated = False

            lines = f.readlines()
            for i in reversed(range(len(lines))):
                line = lines[i].strip()
                if line.startswith('#'):
                    continue
                if line.startswith('VISUAL'):
                    if removeSetting:
                        lines[i] = ''
                    else:
                        lines[i] = insert 
                        settingUpdated = True
                        break

            if not settingUpdated:
                lines.append(insert)

        with open(houdiniEnv, 'w') as f:
            f.writelines(lines)

        hou.ui.displayMessage(
            'External editor setting was successfully saved.\n',
            help ='Use "Edit > Configure External Editor"\n'
                  'to change the new setting.',
            details='Editor setting was saved to:\n'
                    '%s\n'
                    'Value:\n'
                    '%s\n' % (houdiniEnv, insert))

    return editor


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-l', '--launch', nargs='?', help='launch with defined editor')
    parser.add_argument('-c', '--config', action='store_true', help='configure external editor')
    args = parser.parse_args()

    if args.config:
        configExternalEditor()
    else:
        editor =  args.launch or hou.getenv('VISUAL') or hou.getenv('EDITOR')

        if not editor:
            option = hou.ui.displayMessage(
                'External editor is not configured.',
                help='Would you like to configure it now?\n\n\n'
                     'Using system default editor.\n',
                details='Configure the VISUAL or EDITOR environment variable.',
                buttons=('Yes', 'No'),
                close_choice=1,
                severity=hou.severityType.ImportantMessage)

            if option == 0:
                editor = configExternalEditor()

            # open using system default
            if not editor:
                if 'darwin' in OS:
                    editor = 'open -WFt'
                elif 'linux' in OS:
                    editor = 'xdg-open'
                else:
                    editor = 'start'

        if len(kwargs['parms']):
            parm = kwargs['parms'][0]
            editParmExternal(editor, parm)

main()