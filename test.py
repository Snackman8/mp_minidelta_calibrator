from graphics import *
import math
import time

W = 500
H = 500
SCALE = W / 140.0
# create the window
win = GraphWin("calibrator", W, H)   # creates new GraphWin object, 500x500 pixels in size
win.setBackground("white")               #  set the background color to blue

def circle(x, y, r, c, fc=None):
    circ = Circle(Point(W / 2 + x * SCALE, H / 2 + y * SCALE), r * SCALE) # creates a new Circle object centered at 50,50 with a radius of 20 pixels
    if fc:
        circ.setFill(fc)
    circ.setOutline(c)             # invoke the setFill method of the Circle object refered to by circ 
    circ.draw(win)                  # draw the circ object to the GraphWin win
    
circle(0, 0, 60, 'blue')

for y in range (-50, 60, 10):
    for x in range(-50, 60, 10):
        if math.sqrt(x * x + y * y) < 55:
            circle(x, y, 5, 'red')
        else:
            circle(x, y, 5, 'black')

# circ = Circle(Point(50,50), 20) # creates a new Circle object centered at 50,50 with a radius of 20 pixels
# circ.setFill("red")             # invoke the setFill method of the Circle object refered to by circ 
# circ.draw(win)                  # draw the circ object to the GraphWin win
# 
# line = Line(Point(0,0), Point(100, 100))
# line.draw(win)

while not win.isClosed():
    win.checkMouse()
    for y in range (-50, 60, 10):
        for x in range(-50, 60, 10):
            if math.sqrt(x * x + y * y) < 55:
                circle(x, y, 5, 'red', 'green')
                z = 5
                print '%f, %f, %f' % (x, y, z)
                time.sleep(1)
            else:
                circle(x, y, 5, 'red', 'grey')
                
    
    pass