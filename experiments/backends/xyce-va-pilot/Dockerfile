# Xyce 7.10 (official release, serial) + Trilinos 12.12.1 + ADMS (Qucs release-2.3.7)
# + /opt/sky130 copied from the Arcadia ngspice bench image.
# Build: docker build -t xyce-7.10-adms:arm64 .
FROM ghcr.io/arcadia-1/circuit-bench-sky130-ngspice@sha256:bd5c425675eb99fc1a2c3bca10b63a871c457613767e2c6984d6c207b3160500 AS sky130

FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gfortran cmake bison flex libfl-dev \
    libblas-dev liblapack-dev libfftw3-dev libsuitesparse-dev \
    autoconf automake libtool git python3 perl wget ca-certificates libxml-libxml-perl \
  && rm -rf /var/lib/apt/lists/*

COPY --from=sky130 /opt/sky130 /opt/sky130

# Sources are pre-downloaded next to this Dockerfile (SHA256 in src/SHA256SUMS)
# Xyce-7.10.tar.gz   93027b1e7dc195538bfb1886f07057ccd6d4be19b7b45943475108c7fb1e587b
#   from https://xyce.sandia.gov/download/1812/ (Xyce 7.10 source, GPL)
# trilinos-12.12.1.tar.gz  fc8c65f192f6dc9a754069919e3fc040640d547ceb4dd8d7efdfb214207ce949
#   from https://github.com/trilinos/Trilinos/archive/refs/tags/trilinos-release-12-12-1.tar.gz
COPY Xyce-7.10.tar.gz trilinos-12.12.1.tar.gz /tmp/src/

# ---------- ADMS (Qucs fork, tag release-2.3.7 = commit 06e1a6cbe1979db94c49e34bc47c0dbe304883db,
# local tarball sha256 04208628962ef552ef5d2b943a264b34bc8c75142d3f3e59604e8adab8d3a160) ----------
COPY adms-release-2.3.7.tar.gz /tmp/src/
RUN mkdir -p /tmp/src/ADMS \
  && tar -xzf /tmp/src/adms-release-2.3.7.tar.gz -C /tmp/src/ADMS --strip-components=1 \
  && echo "06e1a6cbe1979db94c49e34bc47c0dbe304883db" > /ADMS_COMMIT \
  && cd /tmp/src/ADMS && mkdir build && cd build \
  && cmake -DCMAKE_INSTALL_PREFIX=/usr/local .. \
  && make -j"$(nproc)" && make install \
  && admsXml --version

# ---------- Trilinos 12.12.1 serial (minimal set per Xyce building guide) ----------
RUN mkdir -p /tmp/src/Trilinos-src /tmp/build/trilinos && \
    tar -xzf /tmp/src/trilinos-12.12.1.tar.gz -C /tmp/src/Trilinos-src --strip-components=1 && \
    cd /tmp/build/trilinos && \
    SRCDIR=/tmp/src/Trilinos-src && \
    ARCHDIR=/opt/XyceLibs/Serial && \
    FLAGS="-O3 -fPIC" && \
    cmake \
      -DCMAKE_INSTALL_PREFIX=$ARCHDIR \
      -DCMAKE_C_FLAGS:STRING="$FLAGS" \
      -DCMAKE_CXX_FLAGS:STRING="$FLAGS" \
      -DCMAKE_Fortran_FLAGS:STRING="$FLAGS" \
      -DCMAKE_C_COMPILER=gcc \
      -DCMAKE_CXX_COMPILER=g++ \
      -DCMAKE_Fortran_COMPILER=gfortran \
      -DBUILD_SHARED_LIBS=OFF \
      -DTPL_ENABLE_MPI=OFF \
      -DTrilinos_ENABLE_NOX=ON \
      -DNOX_ENABLE_LOCA=ON \
      -DTrilinos_ENABLE_EpetraExt=ON \
      -DEpetraExt_BUILD_BTF=ON \
      -DEpetraExt_BUILD_EXPERIMENTAL=ON \
      -DEpetraExt_BUILD_GRAPH_REORDERINGS=ON \
      -DTrilinos_ENABLE_Ifpack=ON \
      -DTrilinos_ENABLE_AztecOO=ON \
      -DTrilinos_ENABLE_Belos=ON \
      -DTrilinos_ENABLE_Teuchos=ON \
      -DTrilinos_ENABLE_Amesos=ON \
      -DAmesos_ENABLE_KLU=ON \
      -DTrilinos_ENABLE_Sacado=ON \
      -DTrilinos_ENABLE_CXX11=ON \
      -DTrilinos_ENABLE_COMPLEX_DOUBLE=ON \
      -DTrilinos_ENABLE_TrilinosCouplings=ON \
      -DTrilinos_ENABLE_Kokkos=ON \
      -DTrilinos_ENABLE_ALL_OPTIONAL_PACKAGES=OFF \
      -DTrilinos_ENABLE_TESTS=OFF \
      -DTrilinos_ENABLE_EXAMPLES=OFF \
      -DTPL_ENABLE_AMD=ON \
      -DAMD_LIBRARY_DIRS="/usr/lib/x86_64-linux-gnu;/usr/lib/aarch64-linux-gnu" \
      -DTPL_AMD_INCLUDE_DIRS="/usr/include/suitesparse" \
      -DTPL_ENABLE_BLAS=ON \
      -DTPL_ENABLE_LAPACK=ON \
      $SRCDIR && \
    make -j"$(nproc)" && make install

# ---------- Xyce 7.10 serial, shared + shareable (needed for buildxyceplugin) ----------
RUN mkdir -p /tmp/src/Xyce-src /tmp/build/xyce && \
    tar -xzf /tmp/src/Xyce-7.10.tar.gz -C /tmp/src/Xyce-src --strip-components=1 && \
    cd /tmp/src/Xyce-src && ./bootstrap && \
    cd /tmp/build/xyce && \
    /tmp/src/Xyce-src/configure \
      CXXFLAGS="-O3" \
      ARCHDIR=/opt/XyceLibs/Serial \
      CPPFLAGS="-I/usr/include/suitesparse" \
      --enable-shared \
      --enable-xyce-shareable \
      --prefix=/opt/Xyce-7.10 \
    && make -j"$(nproc)" && make install

ENV PATH=/opt/Xyce-7.10/bin:$PATH
RUN Xyce -v && ls /opt/Xyce-7.10/share/xml | head && ls /opt/Xyce-7.10/bin
