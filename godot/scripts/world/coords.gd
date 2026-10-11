class_name Coords
extends RefCounted
## Blender (Z-up) <-> Godot (Y-up) conversions and the binding camera math
## (scripts/blender/spec/SCHEMA.md, "Camera math").
##
## godot (x, y, z) = blender (x, z, -y); godot rotation.y (rad) = radians(blender yaw_deg).
## Yaw 0 faces Blender +Y = Godot -Z; positive yaw turns counter-clockwise seen from above.


static func blender_to_godot(v: Vector3) -> Vector3:
	return Vector3(v.x, v.z, -v.y)


static func godot_to_blender(v: Vector3) -> Vector3:
	return Vector3(v.x, -v.z, v.y)


## Blender yaw (deg) of a Godot node's facing (its -Z axis), in [0, 360).
static func yaw_deg_from_basis(basis: Basis) -> float:
	var fwd := -basis.z
	return fposmod(rad_to_deg(atan2(-fwd.x, -fwd.z)), 360.0)


## Unit forward vector in Godot space for a Blender yaw.
static func forward_from_yaw_deg(yaw_deg: float) -> Vector3:
	var a := deg_to_rad(yaw_deg)
	return Vector3(-sin(a), 0.0, -cos(a))


## Camera transform per the binding math: -Z looks at `target` with world +Y as up,
## then roll about the camera's local +Z (Blender convention: r' = cos(roll) r + sin(roll) u).
## Godot's Transform3D.looking_at() yields x = f x up (= r) and y = r x f (= u), i.e. the same
## right-handed frame the SCHEMA builds in Blender coordinates.
static func view_transform(position: Vector3, target: Vector3, roll_deg: float) -> Transform3D:
	var t := Transform3D(Basis.IDENTITY, position)
	var dir := target - position
	if dir.length_squared() < 1e-10:
		return t
	var up := Vector3.UP
	if absf(dir.normalized().dot(up)) > 0.9999:
		up = Vector3.BACK
	t = t.looking_at(target, up)
	t.basis = t.basis * Basis(Vector3.BACK, deg_to_rad(roll_deg))
	return t


static func to_vec3(value: Variant, fallback: Vector3 = Vector3.ZERO) -> Vector3:
	if value is Array:
		var a := value as Array
		if a.size() >= 3:
			return Vector3(float(a[0]), float(a[1]), float(a[2]))
	return fallback


static func to_array(v: Vector3, decimals: int = 4) -> Array:
	var s := pow(10.0, decimals)
	return [roundf(v.x * s) / s, roundf(v.y * s) / s, roundf(v.z * s) / s]


## Even-odd point-in-polygon test (polygon in the Godot XZ plane).
static func point_in_polygon(p: Vector2, poly: PackedVector2Array) -> bool:
	var inside := false
	var n := poly.size()
	var j := n - 1
	for i in n:
		var a := poly[i]
		var b := poly[j]
		if (a.y > p.y) != (b.y > p.y):
			var x_cross := a.x + (p.y - a.y) * (b.x - a.x) / (b.y - a.y)
			if p.x < x_cross:
				inside = not inside
		j = i
	return inside
