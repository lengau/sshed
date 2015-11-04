FIRST_DIFF_HEADER = [
    b'--- tmp    2015-05-29 16:46:52.722077075 -0400\n',
    b'+++ tmp2    2015-06-05 20:28:39.700598812 -0400\n',
]

FIRST_DIFF_HUNKS = [
    [
        b'@@ -1,5 +1,2 @@\n',
        b' First line\n',
        b'-Second line\n',
        b'-third line\n',
        b'-fourth line\n',
        b'-fifth lyne\n',
        b'+Fifth line.\n',
    ], [
        b'@@ -18,4 +15,9 @@\n',
        b' Shared data here.\n',
        b'-A removed line.\n',
        b'+Added line\n',
        b' Shared line\n',
        b' Mystery line\n',
        b'+Fifth line\n',
        b'+6\n',
        b'+7\n',
        b'+8\n',
        b'+9\n',
    ]
]

FIRST_DIFF = FIRST_DIFF_HEADER + sum(FIRST_DIFF_HUNKS, [])
