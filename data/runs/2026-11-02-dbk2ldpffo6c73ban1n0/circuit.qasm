OPENQASM 3.0;
include "stdgates.inc";
qubit[1] q;
bit[1] c;
rz(1.5707963267948966) q[0];
sx q[0];
rz(1.5707963267948966) q[0];
c[0] = measure q[0];
