import gnubg, json
for fm in (0, 1):
    for owner in (-1, 0, 1):
        try:
            d = gnubg.cubeinfo(1, owner, fm, 0, (0, 0), 0, 0)
            print("fm=%d owner=%d ->" % (fm, owner), d)
        except Exception as e:
            print("fm=%d owner=%d -> ERR %s" % (fm, owner, e))
