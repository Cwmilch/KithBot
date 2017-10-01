# Script used to quickly paste link to Dropbox file if needed, writes contents of clipboard to the file with the link
from tkinter import Tk

r = Tk()
clip = r.selection_get(selection="CLIPBOARD")
with open('C:/Users/carte/Dropbox/dropbox code.txt', 'w') as f:
    f.write(clip)
