# Failure-mode demo: a general-purpose stroker (Skia) gives different point
# counts at different widths, so its raw output can't be used as masters.
import pathops
def pts(p):
    p.convertConicsToQuads()
    return sum(len(s[1]) for s in p.segments)
for w in (27, 53, 80, 120):
    p = pathops.Path(); p.moveTo(240,480); p.lineTo(400,640); p.lineTo(720,320)
    p.stroke(w, pathops.LineCap.BUTT_CAP, pathops.LineJoin.ROUND_JOIN, 4)
    print(" check width", w, "points", pts(p))
for w in (27, 53, 80, 120):
    p = pathops.Path(); p.moveTo(480,160)
    p.cubicTo(656,160,800,304,800,480); p.cubicTo(800,656,656,800,480,800)
    p.cubicTo(304,800,160,656,160,480); p.cubicTo(160,304,304,160,480,160); p.close()
    p.stroke(w, pathops.LineCap.BUTT_CAP, pathops.LineJoin.ROUND_JOIN, 4)
    print(" ring width", w, "points", pts(p))
