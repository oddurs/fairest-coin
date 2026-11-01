OPENQASM 3.0;
include "stdgates.inc";
qubit[1] q;
bit[1] c;
rz(pi/2) q[0];
sx q[0];
rz(pi/2) q[0];
c[0] = measure q[0];
