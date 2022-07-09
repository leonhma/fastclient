Setup
=====

To install this package, run:

.. code-block:: bash 

    pip install fastclient

To install the latest testing version (may contain bugs), run:

.. code-block:: bash

    pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ fastclient

.. note:: 

    On some systems (especially linux), :code:`pip` may be known as :code:`pip3`

Developing Setup
----------------

If you want to set this package up for directly editing it's source code (for contributing):

1. Clone the package

    .. code-block:: bash

        git clone https://github.com/leonhma/fastclient

2. Create a dynamic link
    This will make the package dynamically update with your local changes:

    .. code-block:: bash

        pip install -e .
