import numpy as np
from scipy import optimize
import pandas as pd
import torch, IPython, itertools, string
import random, time, warnings
import matplotlib.pyplot as plt
from matplotlib import animation
from munch import Munch

class Parameter(torch.nn.Module):
    def __init__(self, tensor, locked=False):
        super(Parameter, self).__init__()
        self.locked = locked
        if self.locked:
            self.tensor = torch.tensor(tensor, requires_grad=False).to(torch.float)
        else:
            self.tensor = torch.nn.Parameter(torch.tensor(tensor).to(torch.float)) 
        
    def __call__(self):
        return(self.tensor)

class Point(torch.nn.Module):
    def __init__(self, linkage, name):
        super(Point, self).__init__()
        self.linkage = linkage
        self.name = name
        self.params = Munch({})
        
    def __repr__(self):
        raise Exception('Override this method.')
    
    @property
    def r(self):
        raise Exception('Override this property.')

    def root(self):
        raise Exception('Override this method.')
    
    def E(self):
        raise Exception('Override this method.')
        
    def add_frompointline(self, L, theta, phi=None, ux=None, uz=None, locked=False):
        new_line = self.linkage.add_frompointline(self, L, theta, phi, ux, uz, locked)
        return(new_line)
    
    def add_onpointline(self, L, theta, phi=None, ux=None, uz=None, beta=None):
        new_line = self.linkage.add_onpointline(self, L, theta, phi, ux, uz, beta)
        return(new_line)
    
class AtPoint(Point):
    def __init__(self, linkage, name, at):
        super(AtPoint, self).__init__(linkage, name)
        self.params.r = Parameter(at, locked=False)
    
    def __repr__(self):
        label = self.__class__.__name__[:-5]
        return('[{}]Point_{}(at={})'.format(label, self.name, str(self.r.tolist())))
    
    @property
    def r(self):
        return(self.params.r())
    
    def root(self):
        return(self)
    
    def E(self):
        return(0)
    
class AnchorPoint(Point):
    def __init__(self, linkage, name, at):
        super(AnchorPoint, self).__init__(linkage, name)
        self.params.r = Parameter(at, locked=True)
        
    def __repr__(self):
        label = self.__class__.__name__[:-5]
        return('[{}]Point_{}(at={})'.format(label, self.name, str(self.r.tolist())))
        
    @property
    def r(self):
        return(self.params.r())
        
    def root(self):
        return(self)
    
    def E(self):
        return(0)
    
class OnPointPoint(Point):
    def __init__(self, linkage, name, parent):
        super(OnPointPoint, self).__init__(linkage, name)
        self.parent = parent
        
    def __repr__(self):
        label = self.__class__.__name__[:-5]
        return('[{}]Point_{}(on={})'.format(label, self.name, str(self.parent)))
        
    @property
    def r(self):
        return(self.parent.r)
    
    def root(self):
        return(self.parent.root())
    
    def E(self):
        return(0)
    
class ToPointPoint(Point):
    def __init__(self, linkage, name, at, parent):
        super(ToPointPoint, self).__init__(linkage, name)
        self.params.r = Parameter(at, locked=False)
        self.parent = parent
        
    def __repr__(self):
        label = self.__class__.__name__[:-5]
        return('[{}]Point_{}(to={})'.format(label, self.name, str(self.parent)))
        
    @property
    def r(self):
        return(self.params.r())
    
    def root(self):
        return(self)
    
    def E(self):
        return((self.r-self.parent.r).pow(2).sum())
    
class CalculatedPoint(Point):
    def __init__(self, linkage, name, parent):
        super(CalculatedPoint, self).__init__(linkage, name)
        self.parent = parent
        
    def __repr__(self):
        label = self.__class__.__name__[:-5]
        return('[{}]Point_{}(from={})'.format(label, self.name, str(self.parent.p1)))
        
    @property
    def r(self):
        if self.parent.ux is None:
            ax = torch.tensor([1,0,0], requires_grad=False).to(torch.float)
        elif type(self.parent.ux) is list:
            ax = torch.tensor(ux, requires_grad=False).to(torch.float)
        elif type(self.parent.ux).__bases__[0].__name__ is 'Line':
            ax = self.parent.ux.u
        else:
            raise Exception('ux must be None, a list, or a Line.')
        if self.parent.uz is None:
            az = torch.tensor([0,0,1], requires_grad=False).to(torch.float)
        elif type(self.parent.uz) is list:
            az = torch.tensor(uz, requires_grad=False).to(torch.float)
        elif type(self.parent.uz).__bases__[0].__name__ is 'Line':
            az = self.parent.uz.u
        else:
            raise Exception('uz must be None, a list, or a Line.')
        ay = torch.cross(az, ax)
        theta = self.parent.params.theta()*10
        phi = self.parent.params.phi()*10
        ux = torch.sin(phi)*torch.cos(theta)
        uy = torch.sin(phi)*torch.sin(theta)
        uz = torch.cos(phi)
        dr = self.parent.L * torch.cat([ux, uy, uz])
        R = torch.stack([ax, ay, az], dim=1)
        r = self.parent.p1.r + torch.matmul(R,dr)
        return(r)
    
    def root(self):
        return(self)
    
    def E(self):
        return(0)
    
class CalculatedAnteriorPoint(Point):
    def __init__(self, linkage, name, parent):
        super(CalculatedAnteriorPoint, self).__init__(linkage, name)
        self.parent = parent
        
    def __repr__(self):
        label = self.__class__.__name__[:-5]
        return('[{}]Point_{}(from={})'.format(label, self.name, str(self.parent.parent)))
        
    @property
    def r(self):
        if self.parent.ux is None:
            ax = torch.tensor([1,0,0], requires_grad=False).to(torch.float)
        elif type(self.parent.ux) is list:
            ax = torch.tensor(ux, requires_grad=False).to(torch.float)
        elif type(self.parent.ux).__bases__[0].__name__ is 'Line':
            ax = self.parent.ux.u
        else:
            raise Exception('ux must be None, a list, or a Line.')
        if self.parent.uz is None:
            az = torch.tensor([0,0,1], requires_grad=False).to(torch.float)
        elif type(self.parent.uz) is list:
            az = torch.tensor(uz, requires_grad=False).to(torch.float)
        elif type(self.parent.uz).__bases__[0].__name__ is 'Line':
            az = self.parent.uz.u
        else:
            raise Exception('uz must be None, a list, or a Line.')
        ay = torch.cross(az, ax)
        theta = self.parent.params.theta()*10
        phi = self.parent.params.phi()*10
        ux = torch.sin(phi)*torch.cos(theta)
        uy = torch.sin(phi)*torch.sin(theta)
        uz = torch.cos(phi)
        dr = self.parent.L * torch.cat([ux, uy, uz])
        R = torch.stack([ax, ay, az], dim=1)
        r = self.parent.parent.r - self.parent.params.beta() * torch.matmul(R,dr)
        return(r)
    
    def root(self):
        return(self)
    
    def E(self):
        return(0)
    
class CalculatedPosteriorPoint(Point):
    def __init__(self, linkage, name, parent):
        super(CalculatedPosteriorPoint, self).__init__(linkage, name)
        self.parent = parent
        
    def __repr__(self):
        label = self.__class__.__name__[:-5]
        return('[{}]Point_{}(from={})'.format(label, self.name, str(self.parent.parent)))
        
    @property
    def r(self):
        if self.parent.ux is None:
            ax = torch.tensor([1,0,0], requires_grad=False).to(torch.float)
        elif type(self.parent.ux) is list:
            ax = torch.tensor(ux, requires_grad=False).to(torch.float)
        elif type(self.parent.ux).__bases__[0].__name__ is 'Line':
            ax = self.parent.ux.u
        else:
            raise Exception('ux must be None, a list, or a Line.')
        if self.parent.uz is None:
            az = torch.tensor([0,0,1], requires_grad=False).to(torch.float)
        elif type(self.parent.uz) is list:
            az = torch.tensor(uz, requires_grad=False).to(torch.float)
        elif type(self.parent.uz).__bases__[0].__name__ is 'Line':
            az = self.parent.uz.u
        else:
            raise Exception('uz must be None, a list, or a Line.')
        ay = torch.cross(az, ax)
        theta = self.parent.params.theta()*10
        phi = self.parent.params.phi()*10
        ux = torch.sin(phi)*torch.cos(theta)
        uy = torch.sin(phi)*torch.sin(theta)
        uz = torch.cos(phi)
        dr = self.parent.L * torch.cat([ux, uy, uz])
        R = torch.stack([ax, ay, az], dim=1)
        r = self.parent.parent.r + (1-self.parent.params.beta()) * torch.matmul(R,dr)
        return(r)
    
    def root(self):
        return(self)
    
    def E(self):
        return(0)
    
class Line(torch.nn.Module):
    def __init__(self, linkage, name):
        super(Line, self).__init__()
        self.linkage = linkage
        self.name = name
        self.parent = None
        self.p1 = None
        self.p2 = None
        self.params = Munch({})
        
    def __repr__(self):
        raise Exception('Override this method.')
        
    @property
    def r(self):
        return(self.p2.r-self.p1.r)
    
    def E(self):
        raise Exception('Override this method.')
    
    def is_constrained(self):
        raise Exception('Override this method.')
        
    def add_onlinepoint(self, alpha=None):
        new_point = self.linkage.add_onlinepoint(self, alpha)
        return(new_point)
    
class FromPointLine(Line):
    def __init__(self, linkage, name, parent, L, theta, phi=None, ux=None, uz=None, locked=False):
        super(FromPointLine, self).__init__(linkage, name)
        self.parent = parent
        self.locked = locked
        self.L = L
        self.params.theta = Parameter([theta*np.pi/180/10], locked=self.locked)
        phi = np.pi/2 if phi is None else phi*np.pi/180
        self.params.phi = Parameter([phi/10], locked=True)
        self.ux = ux
        self.uz = uz
        self.p1 = OnPointPoint(self.linkage, '{}.{}'.format(self.name, '1'), parent=parent)
        self.p2 = CalculatedPoint(self.linkage, '{}.{}'.format(self.name, '2'), parent=self)
        
    def __repr__(self):
        label = self.__class__.__name__[:-4]
        return('[{}]Line_{}(p1={}, p2={})'.format(label, self.name, self.p1.name, self.p2.name))
    
    @property
    def u(self):
        return(self.r/self.L)
    
    def E(self):
        return(0)
    
    def is_length_constrained(self):
        return(True)
    
class FromPointsLine(Line):
    def __init__(self, linkage, name, parent1, parent2):
        super(FromPointsLine, self).__init__(linkage, name)
        self.p1 = OnPointPoint(self.linkage, '{}.{}'.format(self.name, '1'), parent=parent1)
        self.p2 = OnPointPoint(self.linkage, '{}.{}'.format(self.name, '2'), parent=parent2)
        self.target_length = None
        
    def __repr__(self):
        label = self.__class__.__name__[:-4]
        return('[{}]Line_{}(p1={}, p2={})'.format(label, self.name, self.p1.name, self.p2.name))
    
    def E(self):
        if self.is_length_constrained() and self.target_length is not None:
            E = ((self.p2.r-self.p1.r).pow(2).sum().pow(0.5)-self.target_length).pow(2)
            return(E)
        return(0)
    
    def is_length_constrained(self):
        if self.target_length is not None:
            return(True)
        elif self.p1.root().__class__.__name__ is 'AnchorPoint':
            if self.p2.root().__class__.__name__ is 'AnchorPoint':
                return(True)
        return(False)
    
    def constrain_length(self, L):
        if self.p1.root().__class__.__name__ is 'AnchorPoint':
            if self.p2.root().__class__.__name__ is 'AnchorPoint':
                raise Exception('Cannot constrain the length of a line with anchored endpoints.')
        self.target_length = L
        self.linkage.update()
    
class OnLinePoint(Point):
    def __init__(self, linkage, name, parent, alpha):
        super(OnLinePoint, self).__init__(linkage, name)
        self.parent = parent
        alpha = 0.5 if alpha is None else alpha
        self.params.alpha = Parameter([alpha], locked=False)
        
    def __repr__(self):
        label = self.__class__.__name__[:-5]
        return('[{}]Point_{}(on={})'.format(label, self.name, str(self.parent)))
    
    @property
    def r(self):
        return((1-self.params.alpha())*self.parent.p1.r+self.params.alpha()*self.parent.p2.r)

    def root(self):
        return(self)
    
    def E(self):
        return(0)
    
class OnPointLine(Line):
    def __init__(self, linkage, name, parent, L, theta, phi=None, ux=None, uz=None, beta=None):
        super(OnPointLine, self).__init__(linkage, name)
        self.parent = parent
        self.L = L
        self.params.theta = Parameter([theta*np.pi/180/10], locked=False)
        phi = np.pi/2 if phi is None else phi*np.pi/180
        self.params.phi = Parameter([phi/10], locked=True)
        self.ux = ux
        self.uz = uz
        beta = 0.5 if beta is None else beta
        self.params.beta = Parameter([beta], locked=False)
        self.p1 = CalculatedAnteriorPoint(self.linkage, '{}.{}'.format(self.name, '1'), parent=self)
        self.p2 = CalculatedPosteriorPoint(self.linkage, '{}.{}'.format(self.name, '2'), parent=self)
        
    def is_length_constrained(self):
        return(True)
    
class Linkage():
    def __init__(self, show_origin=True):       
        self.points = Munch(torch.nn.ModuleDict({}))
        self.lines = Munch(torch.nn.ModuleDict({}))
        self.names = {}
        for _type in ['point', 'line']:
            self.names[_type] = []
            letters = string.ascii_letters[-26:]
            if _type is 'line':
                letters = letters.lower()
            for n in range(3):
                for t in itertools.product(letters, repeat=n):
                    self.names[_type].append(''.join(t))
            self.names[_type] = iter(self.names[_type][1:])
        self.plot = LinkagePlot(self, show_origin)
        self.tolerance = 0.0001
    
    ######################################## Points ########################################
    
    def add_atpoint(self, at):
        name = next(self.names['point'])
        self.points[name] = AtPoint(self, name, at)
        self.plot.update()
        return(self.points[name])
    
    def add_anchorpoint(self, at):
        name = next(self.names['point'])
        self.points[name] = AnchorPoint(self, name, at)
        self.plot.update()
        return(self.points[name])
    
    def add_onpointpoint(self, parent):
        name = next(self.names['point'])
        self.points[name] = OnPointPoint(self, name, parent)
        self.plot.update()
        return(self.points[name])
    
    def add_topointpoint(self, at, parent):
        name = next(self.names['point'])
        self.points[name] = ToPointPoint(self, name, at, parent)
        self.plot.update()
        return(self.points[name])
    
    def add_onlinepoint(self, parent, alpha=None):
        name = next(self.names['point'])
        self.points[name] = OnLinePoint(self, name, parent, alpha)
        self.plot.update()
        return(self.points[name])
    
    ######################################## Lines #########################################
    
    def add_frompointline(self, parent, L, theta, phi=None, ux=None, uz=None, locked=False):
        name = next(self.names['line'])
        self.lines[name] = FromPointLine(self, name, parent, L, theta, phi, ux, uz, locked)
        self.plot.update()
        return(self.lines[name])
    
    def add_frompointsline(self, parent1, parent2):
        name = next(self.names['line'])
        self.lines[name] = FromPointsLine(self, name, parent1, parent2)
        self.plot.update()
        return(self.lines[name])
    
    def add_onpointline(self, parent, L, theta, phi=None, ux=None, uz=None, beta=None):
        name = next(self.names['line'])
        self.lines[name] = OnPointLine(self, name, parent, L, theta, phi, ux, uz, beta)
        self.plot.update()
        return(self.lines[name])
        
    @property
    def N(self):
        N = 0
        N += len(self.points)
        N += 2*len(self.lines)
        return(N)
    
    @property
    def M(self):
        return(len(self.lines))
     
    def param_dict(self):
        parameters = {}
        for point in self.points.values():
            for param_name in point.params.keys():
                param = point.params[param_name]
                for counter, _param in enumerate(param.parameters()):
                    label = 'point_{}_{}_{}'.format(point.name, param_name, counter)
                    parameters[label] = _param
        for line in self.lines.values():
            for param_name in line.params.keys():
                param = line.params[param_name]
                for counter, _param in enumerate(param.parameters()):
                    label = 'line_{}_{}_{}'.format(line.name, param_name, counter)
                    parameters[label] = _param
        return(parameters)
       
    def energy(self):
        E = 0.0
        for point in self.points.values():
            E += point.E()
        for line in self.lines.values():
            E += line.E()
        return(E)
          
    def _energy(self, x):
        E = 0
        return(E)
        
    def _forces(self, x):
        F = np.zeros(len(x))
        return(F)
        
    def _error_vec(self, x):
        f = np.zeros(len(x))
        f[0] += self._energy(x)
        return(x)
        
    def _error_vec_jacobian(x):
        F = self._forces(x)
        J = np.zeros((len(x),len(x)))
        J[0] += F
        return(J)
        
    def update(self, max_num_epochs=10000):
        optimizer = torch.optim.SGD(self.param_dict().values(), lr=0.001)
        for epoch in range(max_num_epochs):
            optimizer.zero_grad()
            E = self.energy()
            E.backward()
            optimizer.step()
            self.plot.E_list.append(E.item())
            if E <= self.tolerance:
                break
        if False:
            if (E > self.tolerance or E.isnan()):
                raise Exception('Could not solve all constraints.')
        self.plot.update()
        time.sleep(0.01)
        
    '''
    def update(self):
        solver = optimize.root(_error_vec, x0=[0,0,0], jac=_error_vec_jacobian, method='hybr')
        self.plot.E_list.append(E.item())
        if (E > self.tolerance or E.isnan()):
            raise Exception('Could not solve all constraints.')
        self.plot.update()
        time.sleep(0.01)
    '''
        
class LinkagePlot():
    def __init__(self, linkage, show_origin=True):
        self.linkage = linkage
        self.origin = torch.tensor([0,0,0])
        self.E_list = [1.0]
        
        # Set up figure and axis
        self.size = 5
        self.lim = 4
        self.fig = plt.figure(figsize=(2*self.size,self.size))
        self.ax1 = self.fig.add_subplot(121, autoscale_on=False,
            xlim=(-self.lim,self.lim),
            ylim=(-self.lim,self.lim))
        self.ax2 = self.fig.add_subplot(122, autoscale_on=False,
            xlim=(0,1),
            ylim=(0,1))
        self.ax1.set_title('Configuration')
        self.ax2.set_title('log10(E)')
        
        if show_origin:
            self.ax1.scatter(
                [self.origin[0]], [self.origin[1]],
                marker='+', s=50, c='black', alpha=1, label='origin')
        
        self.points, self.anchors, self.lines = {}, {}, {}
            
        self.lnE_line, = self.ax2.plot([], [], 'b-', markersize=3, lw=0.5, label='log10(E)')
        time_template = ' t={:.0f}\n E={:.2f}\n T={:.5f}\n theta={:.0f}\n'
        self.time_text = self.ax1.text(0.05, 0.7, '', transform=self.ax1.transAxes)
        
    def update(self):
        
        for point_name in self.linkage.points.keys():
            #print('point', point_name)
            if self.linkage.points[point_name].__class__.__name__ is 'AnchorPoint':
                color = 'blue'
                size = 150
            else:
                color = 'limegreen'
                size = 50
            if point_name not in self.points.keys():
                point = self.ax1.scatter([], [], s=size, c=color,
                    zorder=0, label=point_name)
                self.points[point_name] = point
            point = self.linkage.points[point_name]
            self.points[point_name].set_offsets(
                [[point.r[0],point.r[1]]])
                
        for line_name in self.linkage.lines.keys():
            #print('line', line_name)
            ls, lw = ':', 1
            if self.linkage.lines[line_name].is_length_constrained():
                ls, lw = '-', 1
            if line_name not in self.lines.keys():
                line, = self.ax1.plot([], [], linestyle=ls, markersize=3, lw=lw, c='black',
                    zorder=0, label=line_name)
                self.lines[line_name] = line
            line = self.linkage.lines[line_name]
            self.lines[line_name].set_data(
                [line.p1.r[0],line.p2.r[0]],
                [line.p1.r[1],line.p2.r[1]])
            self.lines[line_name].set_linestyle(ls)
            self.lines[line_name].set_linewidth(lw)
            for p in [line.p1, line.p2]:
                #print('line_point', line_name, p.name)
                if p.name not in self.points.keys():
                    point = self.ax1.scatter([], [], s=10, c='red',
                        zorder=0, label=p.name)
                    self.points[p.name] = point
                self.points[p.name].set_offsets(
                    [[p.r[0],p.r[1]]])
            
        self.lnE_line.set_xdata(torch.arange(0,len(self.E_list)))
        self.lnE_line.set_ydata(torch.log10(torch.tensor(self.E_list)))
        self.ax2.set_xlabel('Epoch')
        self.ax2.set_xlim(0,len(self.E_list))
        self.ax2.set_ylim(-10,10)
        self.time_text.set_text('')
        self.fig.canvas.draw()