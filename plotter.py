import argparse
import os
from mpl_toolkits.mplot3d import Axes3D
import matplotlib.pyplot as plt
import pandas as pd


# --------------------------------------------------
# Functions
# --------------------------------------------------
def show_figure(filename):
    # load the data
    df = pd.read_csv(filename)
    
    # configure the plot
    fig = plt.figure(num=filename)

    ax = fig.add_subplot(111, projection='3d')
    ax.plot_trisurf(df['X'], df['Y'], df['Z'], color='r')
    ax.set_xlabel('X Label')
    ax.set_ylabel('Y Label')
    ax.set_zlabel('Z Label')


# --------------------------------------------------
# Main
# --------------------------------------------------
if __name__ == '__main__':
    # parse the arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("filename", nargs='?', default='.', help="name of file containing data")
    args = parser.parse_args()

    # sanity check
    if not os.path.exists(args.filename):
        raise Exception("'%s' is not a filename or a directory" % args.filename)
    
    if os.path.isfile(args.filename):
        show_figure(args.filename)
    else:
        for filename in os.listdir(args.filename):
            if filename.startswith('bed') and filename.endswith('csv'):
                show_figure(os.path.join(args.filename, filename))
            
    # show the plot
    plt.show()
