from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from django.http import HttpResponse

def plot_png(view):

    def wrapper(*args, **kwargs):
        fig = view(*args, **kwargs)
        canvas = FigureCanvas(fig)
        response = HttpResponse(content_type='image/png')
        canvas.print_png(response)
        return response

    return wrapper
        
def plot_svg(view):

    def wrapper(*args, **kwargs):
        fig = view(*args, **kwargs)
        canvas = FigureCanvas(fig)
        response = HttpResponse(content_type='image/svg+xml')
        canvas.print_svg(response)
        return response

    return wrapper

##################################################################

class plot_format(object):
    
    extension = 'xxx'
    mime = 'xxx/xxx'    
    
    def __init__(self, view):
        self.view = view
    
    def __call__(self, *args, **kwargs):
        fig = self.view(*args, **kwargs)
        response=HttpResponse(content_type=self.mime)
        fig.savefig(response,
                    format=self.extension,
                    bbox_inches="tight",
                    pad_inches=.05,
                    edgecolor="white")
        return response
    
class plot_svg2(plot_format):
    extension = 'svg'
    mime = 'image/svg+xml'
    
class plot_png2(plot_format):    
    extension = 'png'
    mime = 'image/png'
