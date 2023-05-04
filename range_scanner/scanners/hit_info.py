import bpy
from mathutils import Vector


class HitInfo:
    r"""Stores information about a hit."""

    def __init__(self, location: Vector, faceNormal: Vector, faceIndex: int, distance: float, target: bpy.types.Object):
        r"""Initializes a new instance of the HitInfo class.

        Parameters
        ----------
        location : Vector
            The location of the hit.
        faceNormal : Vector
            The normal of the face that was hit.
        faceIndex : int
            The index of the face that was hit.
        distance : float
            The distance from the origin to the hit.
        target : Object
            The object that was hit.
        """
        self.location = location
        self.faceNormal = faceNormal
        self.faceIndex = faceIndex
        self.distance = distance
        self.target = target
        self.color = None
        self.intensity = None

        self.noiseLocation = None
        self.noiseDistance = None

        self.wasReflected = False

        self.x = None
        self.y = None

        self.partID = None
        self.categoryID = None
