import socket
import argparse

def send(data, port=29500, addr='224.0.1.0'):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 33)
    s.sendto(data, (addr, port))

def recv(port=29500, addr="224.0.1.0", buf_size=1024):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

    except AttributeError:
        pass

    s.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_TTL, 33)
    s.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_LOOP, 1)
    
    s.bind(('', port))

    intf = socket.gethostbyname(socket.gethostname())
    s.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_IF, socket.inet_aton(intf))
    s.setsockopt(socket.SOL_IP, socket.IP_ADD_MEMBERSHIP, socket.inet_aton(addr) + socket.inet_aton(intf))

    data, sender_addr = s.recvfrom(buf_size)
    s.setsockopt(socket.SOL_IP, socket.IP_DROP_MEMBERSHIP, socket.inet_aton(addr) + socket.inet_aton('0.0.0.0'))
    s.close()
    if not data:
        print('Broken')
    else:
        print('Yay')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', help='server or client?', type=int, default=0)
    args = parser.parse_args()

    if args.mode == 0:
        recv()

    else:
        send(b'robot')



