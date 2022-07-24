#!/usr/bin/env python
# Test environment: Python 3.8.10


class OuterClass:
    class InnerClass:
        VAR_A = "contents_a"
        VAR_B = "contents_b"

    # Test 1: succeeds, and prints: ['VAR_A', 'VAR_B']
    print([x for x in vars(InnerClass) if not x.startswith("_")])

    # Test 2: succeeds; prints "contents_a", "contents_b" in turn
    for x in vars(InnerClass):
        if not x.startswith("_"):
            print(getattr(InnerClass, x))  # showing getattr works

    # Test 3: nothing wrong here; prints ['hello', 'hello']
    print(["hello" for x in vars(InnerClass) if not x.startswith("_")])

    # Test 4: raises: NameError: name 'InnerClass' is not defined
    print(
        [
            getattr(InnerClass, x)  # raises here; why?
            for x in vars(InnerClass)
            if not x.startswith("_")
        ]
    )


# Test 5: if you comment out Test 4, this is fine: prints
# ['contents_a', 'contents_b']
print(
    [
        getattr(OuterClass.InnerClass, x)
        for x in vars(OuterClass.InnerClass)
        if not x.startswith("_")
    ]
)


# Aha. Here's the relevant question:
# https://stackoverflow.com/questions/13905741
