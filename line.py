import torch
import numpy as np
from base import BaseGeometry
from param import Parameter, ManualParameter
from point import (
    Point, AtPoint, AnchorPoint, OnPointPoint, ToPointPoint, OnLinePoint,
    CalculatedAlphaPoint, CalculatedAnteriorPoint, CalculatedPosteriorPoint)

class Line(BaseGeometry):
    def __init__(self, linkage, name):
        super(Line, self).__init__(linkage, name)
        self.parent = None
        self.p1 = None
        self.p2 = None
        
    @property
    def r(self):
        return(self.p2.r-self.p1.r)
    
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
        phi = np.pi/2 if phi is None else phi*np.pi/180
        self.ux = ux
        self.uz = uz
        self.p1 = OnPointPoint(self.linkage, '{}.{}'.format(self.name, '1'), parent=parent)
        self.p2 = CalculatedAlphaPoint(self.linkage, '{}.{}'.format(self.name, '2'), parent=self)
        self.params.theta = Parameter([theta*np.pi/180/10], locked=self.locked)
        self.params.phi = Parameter([phi/10], locked=True)
        self._params.theta = ManualParameter([theta*np.pi/180/10], locked=self.locked)
        self._params.phi = ManualParameter([phi/10], locked=True)
        
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
            #E = ((self.p2.r-self.p1.r).pow(2).sum().pow(0.5)-self.target_length).pow(2)
            E = (self.p2.r-self.p1.r).pow(2).sum()-torch.tensor(self.target_length).pow(2)
            E = (torch.abs(E)).pow(0.5)
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
        
class OnPointLine(Line):
    def __init__(self, linkage, name, parent, L, theta, phi=None, ux=None, uz=None, beta=None):
        super(OnPointLine, self).__init__(linkage, name)
        self.parent = parent
        self.L = L
        phi = np.pi/2 if phi is None else phi*np.pi/180
        self.ux = ux
        self.uz = uz
        beta = 0.5 if beta is None else beta
        self.p1 = CalculatedAnteriorPoint(self.linkage, '{}.{}'.format(self.name, '1'), parent=self)
        self.p2 = CalculatedPosteriorPoint(self.linkage, '{}.{}'.format(self.name, '2'), parent=self)
        self.params.theta = Parameter([theta*np.pi/180/10], locked=False)
        self.params.phi = Parameter([phi/10], locked=True)
        self.params.beta = Parameter([beta], locked=False)
        self._params.theta = ManualParameter([theta*np.pi/180/10], locked=False)
        self._params.phi = ManualParameter([phi/10], locked=True)
        self._params.beta = ManualParameter([beta], locked=False)
        
    def is_length_constrained(self):
        return(True)
    
    @property
    def u(self):
        return(self.r/self.L)
    
    def E(self):
        return(0)